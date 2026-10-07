$.widget.bridge("uibutton", $.ui.button);

(function($) {
    "use strict";

    const THEME_STORAGE_KEY = "theme";
    const DARK_CLASS = "dark-mode";
    let updatingThemeAttr = false;

    function getStoredTheme() {
        try {
            return localStorage.getItem(THEME_STORAGE_KEY);
        } catch (error) {
            return null;
        }
    }

    function storeTheme(value) {
        try {
            localStorage.setItem(THEME_STORAGE_KEY, value);
        } catch (error) {
            // Sin almacenamiento disponible, no persistimos la preferencia.
        }
    }

    function prefersDark() {
        if (typeof window.matchMedia !== "function") {
            return false;
        }
        return window.matchMedia("(prefers-color-scheme: dark)").matches;
    }

    function resolveTheme(theme) {
        if (theme === "dark") {
            return "dark";
        }
        if (theme === "auto") {
            return prefersDark() ? "dark" : "light";
        }
        return "light";
    }

    function updateDarkModeIcon(isDark) {
        const icon = $("#darkmode_icon");
        if (!icon.length) {
            return;
        }
        icon.toggleClass("fas", isDark)
            .toggleClass("far", !isDark)
            .attr("title", isDark ? "Cambiar a modo claro" : "Cambiar a modo oscuro");
    }

    function setBodyThemeClass(theme) {
        const isDark = theme === "dark";
        $("body").toggleClass(DARK_CLASS, isDark);
        updateDarkModeIcon(isDark);
    }

    // La preferencia de tema se guarda **solo** en el navegador (D-RED-07 = A,
    // RED-75): acá vivía `sendThemePreference`, que posteaba a `/set_dark_mode/`,
    // una ruta que nunca existió en el URLconf. Cada cambio de tema era un 404 que
    // el `.fail()` tapaba con un `console.warn`, y `Profile.dark_mode` —el campo
    // que iba a recibirlo— nunca se escribió. El candado está en
    // `users/tests/test_tema.py`.
    function applyTheme(theme, options) {
        const settings = $.extend({persist: true}, options);
        const resolved = resolveTheme(theme);

        updatingThemeAttr = true;
        document.documentElement.setAttribute("data-bs-theme", resolved);
        updatingThemeAttr = false;

        setBodyThemeClass(resolved);

        if (settings.persist) {
            storeTheme(theme);
        }
    }

    function synchronizeFromRootAttr() {
        const rootTheme = document.documentElement.getAttribute("data-bs-theme") || "light";
        setBodyThemeClass(rootTheme);
        if (getStoredTheme() !== "auto") {
            storeTheme(rootTheme);
        }
    }

    function initializeTheme() {
        const storedTheme = getStoredTheme();
        const rootTheme = document.documentElement.getAttribute("data-bs-theme");

        if (storedTheme && storedTheme !== rootTheme) {
            applyTheme(storedTheme, {persist: true});
            return;
        }

        if (rootTheme) {
            setBodyThemeClass(rootTheme);
            if (!storedTheme) {
                storeTheme(rootTheme);
            }
            return;
        }

        const preferred = storedTheme || (prefersDark() ? "dark" : "light");
        applyTheme(preferred, {persist: !storedTheme});
    }

    initializeTheme();

    const rootObserver = new MutationObserver(function(mutations) {
        if (updatingThemeAttr) {
            return;
        }
        mutations.forEach(function(mutation) {
            if (mutation.type === "attributes" && mutation.attributeName === "data-bs-theme") {
                synchronizeFromRootAttr();
            }
        });
    });

    rootObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-bs-theme"],
    });

    window.addEventListener("storage", function(event) {
        if (event.key === THEME_STORAGE_KEY && event.newValue) {
            applyTheme(event.newValue, {persist: false});
        }
    });

    if (typeof window.matchMedia === "function") {
        const colorSchemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const handleColorSchemeChange = function() {
            if (getStoredTheme() === "auto") {
                applyTheme("auto", {persist: false});
            }
        };

        if (typeof colorSchemeQuery.addEventListener === "function") {
            colorSchemeQuery.addEventListener("change", handleColorSchemeChange);
        } else if (typeof colorSchemeQuery.addListener === "function") {
            colorSchemeQuery.addListener(handleColorSchemeChange);
        }
    }

    $(function() {
        const logoutIcon = $("#logout_icon");
        if (logoutIcon.length) {
            logoutIcon.hover(
                function() {
                    $(this).addClass("text-danger").removeClass("text-success");
                },
                function() {
                    $(this).addClass("text-success").removeClass("text-danger");
                },
            );
        }

        const darkModeToggle = $("#darkmode");
        if (darkModeToggle.length) {
            darkModeToggle.on("click", function(event) {
                event.preventDefault();
                const currentTheme = document.documentElement.getAttribute("data-bs-theme") === "dark" ? "dark" : "light";
                const nextTheme = currentTheme === "dark" ? "light" : "dark";
                applyTheme(nextTheme, {persist: true});
            });
        } else {
            updateDarkModeIcon(document.body.classList.contains(DARK_CLASS));
        }

        const sidebarMenu = $(".app-sidebar");

        function hideMenuOpenULs() {
            if ($("body").hasClass("sidebar-collapse")) {
                $(".sidebar-menu .nav-item.menu-open>ul").css("display", "none");
            }
        }

        function showMenuOpenULs() {
            if ($("body").hasClass("sidebar-collapse")) {
                $(".sidebar-menu .nav-item.menu-open>ul").css("display", "block");
            }
        }

        hideMenuOpenULs();

        const sidebarObserver = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === "attributes" && mutation.attributeName === "class") {
                    hideMenuOpenULs();
                }
            });
        });

        sidebarObserver.observe(document.body, {attributes: true});

        sidebarMenu.on("mouseenter", function() {
            showMenuOpenULs();
        });

        sidebarMenu.on("mouseleave", function() {
            hideMenuOpenULs();
        });

        const sidebarElement = document.querySelector("[data-lte-toggle=\"sidebar\"]");
        if (sidebarElement) {
            sidebarElement.addEventListener("open.lte.push-menu", function() {
                $(".sidebar-menu .nav-item.menu-open>ul").css("display", "block");
            });
        }
    });
})(jQuery);

// Sistema global de modales modernos
window.showModernAlert = function(message, type = 'info', title = null) {
    if (window.ModernModal) {
        const titles = {
            success: 'Éxito',
            error: 'Error', 
            warning: 'Advertencia',
            info: 'Información'
        };
        
        window.ModernModal.show({
            type: type,
            title: title || titles[type] || 'Información',
            message: message
        });
    } else {
        if (window.toast) window.toast(type || "info", message);
    }
};

// Reemplazar alert global si ModernModal está disponible
if (typeof window.ModernModal !== 'undefined') {
    window.originalAlert = window.alert;
    window.alert = function(message) {
        window.showModernAlert(message, 'info');
    };
}

// Función para mostrar mensajes de éxito específicos
window.showSuccessMessage = function(message) {
    window.showModernAlert(message, 'success', 'Operación Exitosa');
};

// Función para mostrar errores
window.showErrorMessage = function(message) {
    window.showModernAlert(message, 'error', 'Error');
};

// Función para mostrar advertencias
window.showWarningMessage = function(message) {
    window.showModernAlert(message, 'warning', 'Advertencia');
};

window.mostrarRespuesta = function() {
    const selectElement = document.getElementById("id_nombre3");
    const respuestaDetalle = document.getElementById("respuestaDetalle");

    if (!selectElement || !respuestaDetalle) {
        return;
    }

    const selectedValue = selectElement.value;
    if (selectedValue === "Vos sola") {
        respuestaDetalle.innerText = "Vos sola";
    } else if (selectedValue === "Vos con tu pareja") {
        respuestaDetalle.innerText = "Vos con tu pareja";
    } else if (selectedValue === "Tu pareja sola") {
        respuestaDetalle.innerText = "Tu pareja sola";
    } else {
        respuestaDetalle.innerText = "";
    }
};
