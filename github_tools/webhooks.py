from typing import Dict, List, Set, Tuple

import changelogs
import packaging.version
import whatthepatch
from github import Github
from github.Commit import Commit
from github.CommitStatus import CommitStatus
from github.File import File
from github.GithubException import UnknownObjectException
from github.PullRequest import PullRequest
from github.Repository import Repository
from requirements.requirement import Requirement

from shared import configuration, lazy, redis

PDM_CHECK_CONTEXT = 'pdm/automerge'

@lazy.lazy_property
def get_github() -> Github:
    if not configuration.get_str('github_user') or not configuration.get_str('github_password'):
        return None
    return Github(configuration.get('github_user'), configuration.get('github_password'))

def parse_pr_url(url: str) -> Tuple[str, str, int]:
    split_url = url.split('/')
    return split_url[4], split_url[5], int(split_url[7])

def load_pr(data: dict) -> PullRequest:
    org, repo, pr_number = parse_pr_url(data.get('pull_request', data.get('issue'))['url'])
    g = get_github()
    return g.get_repo(f'{org}/{repo}').get_pull(pr_number)

def load_commit(data: dict) -> Commit:
    pr_data = data.get('pull_request')
    if pr_data is None:
        return None
    org, repo, _ = parse_pr_url(pr_data['url'])
    head = pr_data.get('head')
    g = get_github()
    return g.get_repo(f'{org}/{repo}').get_commit(head.get('sha'))

def get_pr_from_status(data: dict) -> PullRequest:
    g = get_github()
    repo = g.get_repo(data['name'])
    return get_pr_from_commit(repo, data['sha'])

def get_pr_from_commit(repo: Repository, sha: str) -> PullRequest:
    cached = redis.get_list(f'github:head:{sha}')
    if cached:
        try:
            pr = repo.get_pull(cached)
            if pr.head.sha == sha and pr.state == 'open':
                return pr
        except UnknownObjectException:
            pass
    for pr in repo.get_pulls():
        head = pr.head.sha
        redis.store(f'github:head:{head}', pr.number, ex=3600)
        if head == sha:
            return pr
    return None

def set_check(data: dict, status: str, message: str) -> CommitStatus:
    commit = load_commit(data)
    return commit.create_status(state=status, description=message, context=PDM_CHECK_CONTEXT)

def check_for_changelogs(pr: PullRequest) -> None:
    for change in pr.get_files():
        if change.filename == 'requirements.txt':
            lines = build_changelog(change)
            for comment in pr.get_issue_comments():
                if comment.body.startswith('# Changelogs'):
                    # Changelog comment
                    comment.edit(body='\n'.join(lines))
                    break
            else:
                pr.create_issue_comment('\n'.join(lines))

def build_changelog(change: File) -> List[str]:
    lines = ['# Changelogs']
    patch = whatthepatch.parse_patch(change.patch).__next__()
    oldversions: Dict[str, str] = {}
    newversions: Dict[str, str] = {}
    for p in patch.changes:
        if len(p) > 1:
            if p[1] is None:
                req = Requirement.parse(p[2])
                if req.specs:
                    oldversions[req.name] = req.specs[0][1]
                else:
                    lines.append(f'> Warning: {p[0]} is pinned to a specific version.')
            elif p[0] is None:
                req = Requirement.parse(p[2])
                if req.specs:
                    newversions[req.name] = req.specs[0][1]
                else:
                    lines.append(f'> Warning: {p[0]} is pinned to a specific version.')
        else:
            lines.append(f'> Warning: Unknown error.')
    for package in newversions:
        old = packaging.version.parse(oldversions.get(package))
        new = packaging.version.parse(newversions.get(package))
        changes = changelogs.get(package)
        logged = False
        for version_string in changes.keys():
            v = packaging.version.parse(version_string)
            if old < v <= new:
                lines.append(f'## {package} {version_string}')
                lines.append(changes[version_string])
                logged = True
        if not logged:
            lines.append(f'## {package} {new}')
            lines.append('No release notes found.')
    return lines

def check_pr_for_mergability(pr: PullRequest) -> str:
    repo = pr.base.repo
    commit = repo.get_commit(pr.head.sha)
    checks: Dict[str, str] = {}
    blocked = False
    for status in commit.get_statuses():
        print(status)
        if status.context == PDM_CHECK_CONTEXT:
            continue
        if checks.get(status.context) is None:
            checks[status.context] = status.state
            if status.state == 'error' and status.context == 'Codacy/PR Quality Review':
                # Codacy sometimes has... issues.  We don't care enough.
                continue
            if status.state != 'success' and not blocked:
                commit.create_status(state='pending', description=f'Waiting for {status.context}', context=PDM_CHECK_CONTEXT)
                blocked = True

    if blocked:
        # We should only merge master into the PR if it's gonna do something.
        if checks.get('continuous-integration/travis-ci/push') == 'failure' and checks.get('continuous-integration/travis-ci/pr') == 'success':
            update_pr(pr)
        return 'blocked'

    travis_pr = 'continuous-integration/travis-ci/pr'
    if travis_pr not in checks.keys():
        # There's a lovely race condition where, if:
        # 1. travis/push has completed before the PR was made
        # 2. And the label is applied on creation (or author is whitelisted)
        # The PR can be merged before travis is aware of the PR.
        # The solution to this is to hardcode a check for /pr
        commit.create_status(state='pending', description=f'Waiting for {travis_pr}', context=PDM_CHECK_CONTEXT)
        return f'Merge blocked by {travis_pr}'

    labels = [l.name for l in pr.as_issue().labels]
    if 'do not merge' in labels:
        commit.create_status(state='failure', description='Blocked by "do not merge"', context=PDM_CHECK_CONTEXT)
        return 'Do not Merge'

    whitelisted = pr.user in repo.get_collaborators()

    if 'squash when ready' in labels:
        commit.create_status(state='success', description='Ready to squash and merge', context=PDM_CHECK_CONTEXT)
        pr.merge(merge_method='squash')
        return 'good to merge'

    if not whitelisted and not 'merge when ready' in labels:
        commit.create_status(state='success', description='Waiting for "merge when ready"', context=PDM_CHECK_CONTEXT)
        return 'Waiting for label'

    if 'beta test' in labels:
        trying = repo.get_git_ref('heads/trying')
        if trying.object.sha == commit.sha:
            commit.create_status(state='success', description='Deployed to test branch', context=PDM_CHECK_CONTEXT)
            return 'Already deployed'
        trying.edit(commit.sha, True)
        commit.create_status(state='success', description='Deployed to test branch', context=PDM_CHECK_CONTEXT)
        return 'beta test'

    commit.create_status(state='success', description='Ready to merge', context=PDM_CHECK_CONTEXT)
    pr.merge()
    return 'good to merge'

def update_pr(pull: PullRequest) -> None:
    repo = pull.base.repo
    print(f'Checking if #{pull.number} is up to date with master.')
    master = repo.get_branch('master')
    base, head = get_common_tree(repo, master.commit.sha, pull.head.sha)
    if head.issuperset(base):
        print('Up to date')
        return
    print(f'#{pull.number}: {pull.head.ref} is behind.')
    repo.merge(pull.head.ref, 'master', f'Merge master into #{pull.number}')


def get_parents(repo: Repository, sha: str) -> List[str]:
    value = redis.get_list(f'github:parents:{repo.full_name}:{sha}')
    if value is None:
        # print(f'getting parents for {sha}')
        commit = repo.get_commit(sha)
        parents = [p.sha for p in commit.parents]
        redis.store(f'github:parents:{repo.full_name}:{sha}', list(parents), ex=604800)
        return parents
    return value

def get_tree(repo: Repository, head: str, max_depth: int = 0) -> Set[str]:
    full_tree: Set[str] = set()
    to_walk = [head]
    depth = 0
    while to_walk:
        commit = to_walk.pop()
        if commit in full_tree:
            continue
        full_tree.add(commit)
        to_walk.extend(get_parents(repo, commit))
        if max_depth:
            depth = depth + 1
            if depth > max_depth:
                break
    return full_tree

def get_common_tree(repo: Repository, a: str, b: str) -> Tuple[Set[str], Set[str]]:
    depth = 0
    a_tree: Set[str] = set()
    b_tree: Set[str] = set()
    while a_tree.isdisjoint(b_tree):
        depth = depth + 1
        a_tree = get_tree(repo, a, depth)
        b_tree = get_tree(repo, b, depth)
    return a_tree, b_tree
