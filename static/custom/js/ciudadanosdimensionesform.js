document.addEventListener("DOMContentLoaded", function () {
  const INCOMPLETO_OPTION = "Incompleto";
  const maxSelections = 3;

  // Identificadores de contenedores
  const ID_INCOMPLETO_FORM = "#container_incompleto";
  const ID_SIN_EDU_FORMAL = "#container_sin_edu";
  const ID_AREA_CURSO = "#container_area_curso";
  const ID_MAX_NIVEL = "#container_max_nivel";
  const ID_ESTADO_NIVEL = "#container_nivel";
  const ID_DATOS_INSTITUCION = "#container_institucion";
  const ID_DESAGUE_BANIO = "#container_desague";
  const ID_CONVIVIENTE = "#container_conviviente";
  const ID_HS_SEMANALES = "#container_horas_semanales";
  const ID_ACT_REALIZADA_COMO = "#container_actividad_realizada";
  const ID_DURACION_TRABAJO = "#container_duracion_trabajo";
  const ID_APORTE_JUBILACION = "#container_jubilacion";
  const ID_MODO_CONTRATACION = "#container_contratacion";
  const ID_BUSQUEDA_LABORAL = "#container_busqueda_laboral";
  const ID_TIEMPO_BUSQUEDA = "#container_tiempo_busqueda";
  const ID_NO_BUSQUEDA = "#container_no_busqueda";
  const ID_OCUPACION = "#container_ocupacion";
  const ID_PLAN_SOCIAL = "#container_plan_social";

  // Selecciones múltiples con límite
  var selects = document.querySelectorAll('select[name="area_curso"], select[name="area_oficio"], select[name="planes"]');
  selects.forEach(function (select) {
    select.setAttribute('multiple', 'multiple');
    select.addEventListener('change', function () {
      var selectedOptions = Array.from(select.selectedOptions);
      if (selectedOptions.length > maxSelections) {
        if (window.toast) window.toast('warning', 'Solo puedes seleccionar hasta 3 opciones.');
        selectedOptions[selectedOptions.length - 1].selected = false;
      }
    });
  });


  // Formularios
  let estadoNivelForm = document.querySelector('#id_estado_nivel');
  let asisteEscuelaForm = document.querySelector('#id_asiste_escuela');
  let realizando_cursoForm = document.querySelector('#id_realizando_curso');
  let hayBanioForm = document.querySelector("#div_id_hay_banio");
  let tieneTrabajoForm = document.querySelector("#div_id_tiene_trabajo");
  let busqueda_laboralForm = document.querySelector("#id_busqueda_laboral");
  let planSocialForm = document.querySelector("#id_recibe_plan");

  // Estados de formulario
  let asisteEscuelaFormEstados = [
    { valor: "1", mostrar: [ID_MAX_NIVEL, ID_DATOS_INSTITUCION], ocultar: [ID_ESTADO_NIVEL, ID_INCOMPLETO_FORM, ID_SIN_EDU_FORMAL] },
    { valor: "2", mostrar: [ID_MAX_NIVEL, ID_ESTADO_NIVEL, ID_DATOS_INSTITUCION], ocultar: [ID_SIN_EDU_FORMAL] },
    { valor: "3", mostrar: [ID_SIN_EDU_FORMAL], ocultar: [ID_MAX_NIVEL, ID_ESTADO_NIVEL, ID_DATOS_INSTITUCION] }
  ];

  let estadoNivelFormEstados = [
    { valor: INCOMPLETO_OPTION, mostrar: [], ocultar: [] },
    { valor: null, mostrar: [], ocultar: [] }
  ];

  let realizando_cursoFormEstados = [
    { valor: "True", mostrar: [ID_AREA_CURSO], ocultar: [] },
    { valor: "False", mostrar: [], ocultar: [ID_AREA_CURSO] }
  ];

  let hayBanioFormEstados = [
    { valor: '3', mostrar: [], ocultar: [ID_DESAGUE_BANIO] },
    { valor: '4', mostrar: [], ocultar: [ID_DESAGUE_BANIO] },
    { valor: null, mostrar: [ID_DESAGUE_BANIO], ocultar: [] }
  ];

  let tieneTrabajoFormEstados = [
    { valor: "True", mostrar: [ID_HS_SEMANALES, ID_ACT_REALIZADA_COMO, ID_DURACION_TRABAJO, ID_APORTE_JUBILACION, ID_MODO_CONTRATACION], ocultar: [ID_NO_BUSQUEDA, ID_TIEMPO_BUSQUEDA, ID_BUSQUEDA_LABORAL] },
    { valor: "False", mostrar: [ID_BUSQUEDA_LABORAL], ocultar: [ID_HS_SEMANALES, ID_ACT_REALIZADA_COMO, ID_DURACION_TRABAJO, ID_APORTE_JUBILACION, ID_MODO_CONTRATACION, ID_TIEMPO_BUSQUEDA, ID_NO_BUSQUEDA] }
  ];

  let busqueda_laboralFormEstados = [
    { valor: "True", mostrar: [ID_TIEMPO_BUSQUEDA, ID_OCUPACION], ocultar: [ID_NO_BUSQUEDA] },
    { valor: "False", mostrar: [ID_NO_BUSQUEDA], ocultar: [ID_TIEMPO_BUSQUEDA, ID_OCUPACION] }
  ];

  let planSocialFormEstados = [
    { valor: "True", mostrar: [ID_PLAN_SOCIAL], ocultar: [] },
    { valor: "False", mostrar: [], ocultar: [ID_PLAN_SOCIAL] }
  ];

  // Condiciones de cambio
  FormUtils.manejarCambioMostrarOcultar(asisteEscuelaForm, asisteEscuelaFormEstados);
  FormUtils.manejarCambioMostrarOcultar(estadoNivelForm, estadoNivelFormEstados);
  FormUtils.manejarCambioMostrarOcultar(realizando_cursoForm, realizando_cursoFormEstados);
  FormUtils.manejarCambioMostrarOcultar(hayBanioForm, hayBanioFormEstados);
  FormUtils.manejarCambioMostrarOcultar(tieneTrabajoForm, tieneTrabajoFormEstados);
  FormUtils.manejarCambioMostrarOcultar(busqueda_laboralForm, busqueda_laboralFormEstados);
  FormUtils.manejarCambioMostrarOcultar(planSocialForm, planSocialFormEstados);

  // Inicializar estado de formularios
  FormUtils.mostrarOcultar(asisteEscuelaForm.value, asisteEscuelaFormEstados);
  FormUtils.mostrarOcultar(estadoNivelForm.value, estadoNivelFormEstados);
  FormUtils.mostrarOcultar(realizando_cursoForm.value, realizando_cursoFormEstados);
  FormUtils.mostrarOcultar(hayBanioForm.value, hayBanioFormEstados);
  FormUtils.mostrarOcultar(tieneTrabajoForm.value, tieneTrabajoFormEstados);
  FormUtils.mostrarOcultar(busqueda_laboralForm.value, busqueda_laboralFormEstados);
  FormUtils.mostrarOcultar(planSocialForm.value, planSocialFormEstados);

  // Manejo de pregunta id_nivel_incompleto, se maneja aparte
  let preguntasVinculadas = document.querySelectorAll(
    "#id_asiste_escuela, #id_max_nivel, #id_estado_nivel"
  );

  function mostrarOcultarPreguntaEducacionIncompleta() {
    // Calculamos un puntaje acorde al progreso educativo hecho por el encuestado.
    // Obtenemos los valores de los campos y la multiplicación de esos valores nos da un puntaje
    // que de pasar cierto límite nos mostrará o no la pregunta.
    const PUNTAJE_MINIMO = 12;
    let maxNivelValue = document.querySelector("#id_max_nivel").selectedIndex;
    let estadoNivelValue =
      document.querySelector("#id_estado_nivel").selectedIndex;
    let puntaje = maxNivelValue * estadoNivelValue;
    if (asisteEscuelaForm.value != "1" && puntaje < PUNTAJE_MINIMO) {
      FormUtils.mostrar(ID_INCOMPLETO_FORM, true);
    } else {
      FormUtils.mostrar(ID_INCOMPLETO_FORM, false);
    }
  }

  preguntasVinculadas.forEach((elemento) => {
    elemento.addEventListener("change", () => {
      mostrarOcultarPreguntaEducacionIncompleta();
    });
  });

  // Llamamos al inicio para dejar correcta su visualización
  mostrarOcultarPreguntaEducacionIncompleta();
  // Fin manejo de pregunta id_nivel_incompleto

  // Si asisteEscuelaForm es "a", estadoNivel se oculta y por default queda su valor en "En curso"

  function setEstadoNivelEnCurso() {
    if (asisteEscuelaForm.value === "1") {
      estadoNivelForm.selectedIndex = 1;
    } else {
      for (let i = 0; i < estadoNivelForm.options.length; i++) {
        if (estadoNivelForm.options[i].text === "En curso") {
          estadoNivelForm.remove(i);
          break;
        }
      }
    }
  }

  asisteEscuelaForm.addEventListener("change", () => {
    setEstadoNivelEnCurso();
  });

  setEstadoNivelEnCurso();

  document.getElementById('id_provinciaInstitucion').addEventListener('change', function () {
    var url = ajaxLoadMunicipiosUrl;  // Obtén la URL de la vista
    var provinciaId = this.value;  // Obtén el ID de la provincia seleccionada

    fetch(url + '?provincia_id=' + provinciaId)
      .then(response => response.json())
      .then(data => {
        var municipioSelect = document.getElementById('id_municipioInstitucion');
        municipioSelect.innerHTML = '';  // Limpia el campo de municipios

        data.forEach(function (municipio) {
          var option = document.createElement('option');
          option.value = municipio.id;
          option.setAttribute('data-departamento-id', municipio.id);  // Añadir propiedad personalizada
          option.textContent = municipio.nombre;
          municipioSelect.appendChild(option);
        });
      });
  });

  document.getElementById('id_municipioInstitucion').addEventListener('change', function () {
    var url = ajaxLoadLocalidadesUrl;  // Obtén la URL de la vista
    var localidadId = this.options[this.selectedIndex].getAttribute('data-departamento-id');;  // Obtén el ID de la provincia seleccionada

    fetch(url + '?municipio_id=' + localidadId)
      .then(response => response.json())
      .then(data => {
        var localidadSelect = document.getElementById('id_localidadInstitucion');
        localidadSelect.innerHTML = '';  // Limpia el campo de municipios

        data.forEach(function (localidad) {
          var option = document.createElement('option');
          option.value = localidad.id;
          option.textContent = localidad.nombre;
          localidadSelect.appendChild(option);
        });
      });
  });
});

