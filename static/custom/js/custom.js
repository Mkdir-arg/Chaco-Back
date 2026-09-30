

$(function () {
	//Initialize input Elements
	bsCustomFileInput.init();

	//Initialize Select2 Elements
	$('.select2').select2()

	//Initialize Select2 Elements
	$('.custom-select').find('[value=""]').text('');

	$(".print").click(function () {
		//imprime los div excepto los elementos que tengan la clase 'd-print-none'
		window.print();
	});
	$(".clickable-row").click(function () {
		// se agrrega la clase en filas <tr> de un table para que sean links a la vista de detalle del elemento
		window.location = $(this).data("href");
	});

});



$(function () {
	$(".tabladt2")
		.DataTable({
			responsive: true,
			lengthChange: false,
			autoWidth: false,

			language: {
				"decimal": "",
				"emptyTable": "Sin resultados",
				"info": "",
				"infoEmpty": "Mostrando 0 de 0 Entradas",
				"infoFiltered": "(Filtrado de _MAX_ total entradas)",
				"infoPostFix": "",
				"thousands": ",",
				"lengthMenu": "Mostrar _MENU_ Entradas",
				"loadingRecords": "Cargando...",
				"processing": "Procesando...",
				"search": "",
				"searchPlaceholder": "Filtrar resultados",
				"zeroRecords": "<span class='text-muted'>Sin resultados encontrados</span>",
				"buttons": {
					"copy": 'Copiar',
					"print": 'Imprimir',
					"colvis": 'Columnas',
				},
				"paginate": {
					"first": "Primero",
					"last": "Ultimo",
					"next": "Continuar",
					"previous": "Volver",
				}
			},
			"oTableTools": {
				"sSwfPath": "/swf/copy_csv_xls_pdf.swf",
				"aButtons": [
					{
						"sExtends": "copy",
						"sButtonText": "Copiar al portapapeles"
					}
				]
			}

		})
		.buttons()
		.container()
		.appendTo(".dataTables_wrapper .col-md-6:eq(0)");
});

$(function () {
	$(".tabladt")
		.DataTable({
			responsive: true,
			lengthChange: false,
			autoWidth: false,
			pageLength: 20,

			language: {
				decimal: "",
				emptyTable: "Sin resultados",
				info: "Mostrando _START_ a _END_ de <strong> _TOTAL_ Entradas </strong>",
				infoEmpty: "Mostrando 0 de 0 Entradas",
				infoFiltered: "(Filtrado de _MAX_ total entradas)",
				infoPostFix: "",
				thousands: ",",
				lengthMenu: "Mostrar _MENU_ Entradas",
				loadingRecords: "Cargando...",
				processing: "Procesando...",
				search: "",
				searchPlaceholder: "Filtrar resultados",
				zeroRecords:
					"<span class='text-muted'>Sin resultados encontrados</span>",
				buttons: {
					copy: "Copiar",
					print: "Imprimir",
					colvis: "Columnas",
				},
				paginate: {
					first: "Primero",
					last: "Ultimo",
					next: "Continuar",
					previous: "Volver",
				},
			},
			buttons: [
				{
					extend: "copy",
					text: "Copiar",
					exportOptions: {
						columns: ":not(:last-child)",
					},
				},
				{
					extend: "csv",
					text: "CSV",
					exportOptions: {
						columns: ":not(:last-child)",
					},
				},
				{
					extend: "excel",
					text: "Excel",
					exportOptions: {
						columns: ":not(:last-child)",
					},
				},
				{
					extend: "pdf",
					text: "PDF",
					exportOptions: {
						columns: ":not(:last-child)",
					},
				},
				{
					extend: "print",
					text: "Imprimir",
					exportOptions: {
						columns: ":not(:last-child)",
					},
				},
				{
					extend: "colvis",
					text: "Columnas",
					exportOptions: {
						columns: ":not(:last-child)",
					},
				},

				{ exportOptions: { columns: ":not(.notexport)" } },
			],
			oTableTools: {
				sSwfPath: "/swf/copy_csv_xls_pdf.swf",
				aButtons: [
					{
						sExtends: "copy",
						sButtonText: "Copiar al portapapeles",
					},
				],
			},

			dom: 'Bfrtip',  // Si usas el plugin Buttons
			buttons: [
				'copy', 'csv', 'excel', 'pdf', 'print',
				{
					extend: 'colvis',
					columns: ':not(.noVis)'  // Esto asegura que las columnas con la clase 'noVis' no sean parte del control de visibilidad
				}
			],
			columnDefs: [
				{
					targets: [0], // Índice de la columna "Nombre"
					visible: true,
					searchable: false,
					orderable: false,
					className: 'noVis',
				},
			],
		})
		.on("column-visibility.dt", function (e, settings, column, state) {
			var api = new $.fn.dataTable.Api(settings);
			var visibleColumns = api.columns(":visible").count();
			console.log(api.columns(":visible"));
			if (visibleColumns === 0) {
				api.column(column).visible(true);
				if (window.ModernModal) {
					window.ModernModal.show({
						type: 'warning',
						title: 'Columnas Visibles',
						message: 'Debe haber al menos una columna visible en la tabla.'
					});
				} else {
					if (window.toast) window.toast("warning", "Debe haber al menos una columna visible.");
				}
			}
		})
		.buttons()
		.container()
		.appendTo(".dataTables_wrapper .col-md-6:eq(0)");
});

//cambio color del badge del estado del ticket    
$('.badge-gb-color').addClass(function () {
	let dato = $(this).text();

	if (dato == 'Alta') {
		$(this).addClass('bg-warning');
	} else if (dato == 'Urgente') {
		$(this).addClass('bg-orange');
	} else if (dato == 'Muy urgente') {
		$(this).addClass('bg-danger');
	} else {
		$(this).addClass('bg-body-tertiary text-body');
	}
});
