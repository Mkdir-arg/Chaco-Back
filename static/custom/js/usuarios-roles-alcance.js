/*
 * Selector de roles del ABM de Usuarios: frena la combinación de roles cuyo alcance
 * en Becas se pisa (Cambio 332).
 *
 * Contrato (users/templates/user/user_form.html):
 * - contenedor #roles-picker con data-mensaje-roles-se-pisan: el texto del error del
 *   servidor con los marcadores {a} y {b};
 * - cada checkbox [data-rol-check] con data-nombre y, si el rol fija un alcance en
 *   Becas, data-alcance-becas (administrador | referente | coordinador_regional |
 *   coordinador).
 *
 * Al tildar un rol cuyo tipo es distinto del de otro ya tildado, revierte la selección
 * y avisa con ModernModal. Es mejora progresiva: la regla vive en el servidor
 * (users.forms._validar_roles_becas_sin_pisarse), que también cubre los roles que el
 * operador no ve. Escucha en captura sobre el contenedor para revertir antes de que el
 * script del selector recalcule chips y contadores.
 */
(function () {
    'use strict';

    function ordenar(nombres) {
        return nombres.slice().sort(function (x, y) {
            return x.localeCompare(y, 'es', { sensitivity: 'base' });
        });
    }

    function avisar(mensaje) {
        if (window.ModernModal) {
            window.ModernModal.show({
                type: 'warning',
                title: 'Roles que no se pueden combinar',
                message: mensaje,
                confirmText: 'Entendido'
            });
        } else if (typeof window.toast === 'function') {
            window.toast('warning', mensaje);
        }
    }

    function iniciar() {
        var picker = document.getElementById('roles-picker');
        if (!picker) return;
        var plantilla = picker.dataset.mensajeRolesSePisan || '';

        picker.addEventListener('change', function (ev) {
            var check = ev.target;
            if (!check || !check.matches || !check.matches('[data-rol-check]') || !check.checked) return;
            var tipo = check.dataset.alcanceBecas;
            if (!tipo) return;

            var tildados = Array.prototype.slice.call(picker.querySelectorAll('[data-rol-check]:checked'));
            var choque = tildados.find(function (otro) {
                return otro !== check && otro.dataset.alcanceBecas && otro.dataset.alcanceBecas !== tipo;
            });
            if (!choque) return;

            check.checked = false;
            var nombres = ordenar([check.dataset.nombre || '', choque.dataset.nombre || '']);
            avisar(plantilla.replace('{a}', nombres[0]).replace('{b}', nombres[1]));
        }, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
