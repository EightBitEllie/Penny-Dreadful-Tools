from flask_babel import gettext

from logsite.view import View

from .. import APP, BABEL


@APP.route('/about/')
def about():
    view = About()
    return view.page()

# pylint: disable=no-self-use
class About(View):
    def subtitle(self) -> str:
        return gettext('About')

    def languages(self) -> str:
        return ', '.join([locale.display_name for locale in BABEL.list_translations()])
