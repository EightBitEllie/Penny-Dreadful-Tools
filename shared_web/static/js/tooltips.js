/*global Deckbox, $ */
/* Tooltip code originally from https://deckbox.org/help/tooltips and now much hacked around and jQuery dependency introduced. */

// Initialize namespaces.
if (typeof Deckbox === "undefined") Deckbox = {};
Deckbox.ui = Deckbox.ui || {};

/**
 * Main tooltip type.
 */
Deckbox.ui.Tooltip = class ToolTip {
    constructor(className, type) {
        this.el = document.createElement("div");
        this.el.className = `${className} ${type}`;
        this.type = type;
        this.el.style.display = "none";
        document.body.appendChild(this.el);
        this.tooltips = {};
    }

    showImage(posX, posY, image) {
        if (image.complete) {
            this.el.innerHTML = "";
            this.el.appendChild(image);
        } else {
            this.el.innerHTML = "Loading…";
            image.onload = () => {
                const self = Deckbox._.tooltip("image");
                self.el.innerHTML = "";

                image.onload = null;

                self.el.appendChild(image);
                self.move(posX, posY);
            };
        }

        this.el.style.display = "";
        this.move(posX, posY);
    }

    hide() {
        this.el.style.display = "none";
    }

    move(posX, posY) {
        // The tooltip should be offset to the right so that it's not exactly next to the mouse.
        posX += 15;
        posY -= this.el.offsetHeight / 3;

        // Remember these for when (if) the register call wants to show the tooltip.
        this.posX = posX;
        this.posY = posY;

        if (this.el.style.display === "none") return;

        const [left, top] = Deckbox._.fitToScreen(posX, posY, this.el);

        this.el.style.left = `${left}px`;
        this.el.style.top = `${top}px`;
    }

    register(url, content) {
        this.tooltips[url].content = content;

        if (this.tooltips[url].el._shown) {
            this.el.style.width = "";
            this.el.innerHTML = `
                <table>
                    <tr>
                        <td>${content}</td>
                        <th style="background-position: right top;" />
                    </tr>
                    <tr>
                        <th style="background-position: left bottom;" />
                        <th style="background-position: right bottom;" />
                    </tr>
                </table>
            `;
            this.el.style.width = (20 + Math.min(330, this.el.childNodes[0].offsetWidth)) + "px";
            this.move(this.posX, this.posY);
        }
    }

    dispose() {
        document.body.removeChild(this.el);
    }
};

Deckbox.ui.Tooltip.hide = () => {
    Deckbox._.tooltip("image").hide();
    Deckbox._.tooltip("text").hide();
};


Deckbox._ = {
    onDocumentLoad(callback) {
        if (window.addEventListener) {
            window.addEventListener("load", callback, false);
        } else {
            window.attachEvent && window.attachEvent("onload", callback);
        }
    },

    preloadImg(link) {
        const img = document.createElement("img");
        img.style.display = "none";
        img.style.width = "1px";
        img.style.height = "1px";
        img.src = "https://deckbox.org/mtg/" + $(link).text().replace(/^[0-9 ]*/, "") + "/tooltip";

        return img;
    },

    pointerX(event) {
        const docElement = document.documentElement;
        const body = document.body || { scrollLeft: 0 };

        const [input] = (event.touches || [event]);

        return input.pageX ||
            (input.clientX +
                (docElement.scrollLeft || body.scrollLeft) -
                (docElement.clientLeft || 0));
    },

    pointerY(event) {
        const docElement = document.documentElement;
        const body = document.body || { scrollTop: 0 };

        const [input] = (event.touches || [event]);

        return input.pageY ||
            (input.clientY +
                (docElement.scrollTop || body.scrollTop) -
                (docElement.clientTop || 0));
    },

    scrollOffsets() {
        return [
            window.pageXOffset || document.documentElement.scrollLeft || document.body.scrollLeft,
            window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop
        ];
    },

    viewportSize() {
        const ua = navigator.userAgent;
        let rootElement;

        if (ua.indexOf("AppleWebKit/") > -1 && !document.evaluate) {
            rootElement = document;
        } else if (Object.prototype.toString.call(window.opera) === "[object Opera]" && window.parseFloat(window.opera.version()) < 9.5) {
            rootElement = document.body;
        } else {
            rootElement = document.documentElement;
        }

        /* IE8 in quirks mode returns 0 for these sizes. */
        const size = [rootElement["clientWidth"], rootElement["clientHeight"]];
        if (size[1] !== 0) return size;

        return [document.body["clientWidth"], document.body["clientHeight"]];
    },

    fitToScreen(posX, posY, el) {
        const scroll = Deckbox._.scrollOffsets();
        const viewport = Deckbox._.viewportSize();

        /* decide if wee need to switch sides for the tooltip */
        /* too big for X */
        if ((el.offsetWidth + posX) >= (viewport[0] - 15)) {
            posX = posX - el.offsetWidth - 20;
        }

        /* If it's too high, we move it down. */
        if (posY - scroll[1] < 0) {
            posY += scroll[1] - posY + 5;
        }
        /* If it's too low, we move it up. */
        if (posY + el.offsetHeight - scroll[1] > viewport[1]) {
            posY -= posY + el.offsetHeight + 5 - scroll[1] - viewport[1];
        }

        return [posX, posY];
    },

    removeEvent(obj, type, fn) {
        if (obj.removeEventListener) {
            if (type === "mousewheel") obj.removeEventListener("DOMMouseScroll", fn, false);

            obj.removeEventListener(type, fn, false);
        } else if (obj.detachEvent) {
            obj.detachEvent("on" + type, obj[type + fn]);
            obj[type + fn] = null;
            obj["e" + type + fn] = null;
        }
    },

    loadJS(url) {
        const s = document.createElement("s" + "cript");
        s.setAttribute("type", "text/javascript");
        s.setAttribute("src", url);

        document.getElementsByTagName("head")[0].appendChild(s);
    },

    loadCSS(url) {
        const s = document.createElement("link");
        s.type = "text/css";
        s.rel = "stylesheet";
        s.href = url;

        document.getElementsByTagName("head")[0].appendChild(s);
    },

    needsTooltip(el) {
        if ($(el).hasClass("card")) return true;
    },

    tooltip(which) {
        if (which === "image") return this._iT = this._iT || new Deckbox.ui.Tooltip("deckbox_i_tooltip", "image");
        if (which === "text") return this._tT = this._tT || new Deckbox.ui.Tooltip("deckbox_t_tooltip", "text");
    },

    target(event) {
        let target = event.target || event.srcElement || document;

        /* check if target is a textnode (safari) */
        if (target.nodeType === 3) target = target.parentNode;

        return target;
    },

    onpointerover(event) {
        const el = Deckbox._.target(event);

        if (Deckbox._.needsTooltip(el)) {
            const no = el.getAttribute("data-nott");
            const posX = Deckbox._.pointerX(event);
            const posY = Deckbox._.pointerY(event);

            if (!no) {
                el._shown = true;
                const url = $(el).data("tt");

                if (url) {
                    Deckbox._.showImage(el, url, posX, posY);
                }
            }
        }
    },

    showImage(el, url, posX, posY) {
        const img = document.createElement("img");
        url = url.replace(/\?/g, ""); /* Problematic with routes on server. */
        img.src = url;
        img.height = 310;

        setTimeout(() => {
            if (el._shown) Deckbox._.tooltip("image").showImage(posX, posY, img);
        }, 200);
    },

    onpointermove(event) {
        const el = Deckbox._.target(event);
        const posX = Deckbox._.pointerX(event);
        const posY = Deckbox._.pointerY(event);

        if (Deckbox._.needsTooltip(el)) {
            Deckbox._.tooltip("image").move(posX, posY);
        }
    },

    onpointerout(event) {
        const el = Deckbox._.target(event);

        if (Deckbox._.needsTooltip(el)) {
            el._shown = false;
            Deckbox._.tooltip("image").hide();
        }
    },

    click() {
        Deckbox._.tooltip("image").hide();
    },

    enable() {
        document.addEventListener("pointerover", Deckbox._.onpointerover);
        document.addEventListener("pointermove", Deckbox._.onpointermove);
        document.addEventListener("pointerout", Deckbox._.onpointerout);
        document.addEventListener("click", Deckbox._.click);
    },

    dispose() {
        if (this._tT) this._tT.dispose();
        if (this._iT) this._iT.dispose();

        document.removeEventListener("pointerover", Deckbox._.onpointerover);
        document.removeEventListener("pointermove", Deckbox._.onpointermove);
        document.removeEventListener("pointerout", Deckbox._.onpointerout);
        document.removeEventListener("click", Deckbox._.click);
    }
};

/**
 * Call this to initialize or reinitialize (after xhr data load) card mouseover images.
 */
Deckbox.load = () => {
    $(".card").each(() => {
        $(this).data("tt", "https://deckbox.org/mtg/" + $(this).text().replace(/^[0-9 ]*/, "") + "/tooltip");
    });

    const allLinks = Array.from(document.getElementsByTagName("a"));
    allLinks.forEach((link) => {
        if (Deckbox._.needsTooltip(link)) {
            document.body.appendChild(Deckbox._.preloadImg(link));
        }
    });
};

/**
 * Preload images and CSS for maximum responsiveness even though this does unnecessary work on touch devices.
 */
(() => {
    const protocol = (document.location.protocol === "https:") ? "https:" : "http:";
    Deckbox._.loadCSS(protocol + "//deckbox.org/assets/external/deckbox_tooltip.css");
    /* IE needs more shit */
    if (!!window.attachEvent && !(Object.prototype.toString.call(window.opera) === "[object Opera]")) {
        Deckbox._.loadCSS(protocol + "//deckbox.org/assets/external/deckbox_tooltip_ie.css");
    }

    /* Preload the tooltip images. */
    Deckbox._.onDocumentLoad(Deckbox.load);
})();
