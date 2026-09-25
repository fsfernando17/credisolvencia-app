function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = JSON.parse(e.postData.contents);
  
  if (sheet.getLastRow() === 0) {
    sheet.appendRow([
      "Fecha", 
      "Tipo de Crédito", 
      "Condicion", 
      "Producto", 
      "DNI", 
      "N° de Suministro", 
      "Nombre", 
      "Apellidos", 
      "Monto", 
      "¿Aumento?", 
      "%", 
      "Interes", 
      "Tipo", 
      "Monto de cuotas", 
      "N° de cuotas", 
      "Capacidad de pago", 
      "Estado", 
      "Observacion"
    ]);
  }
  
  sheet.appendRow([
    data.fecha,
    data.tipo_credito,
    data.condicion,
    data.producto,
    data.dni,
    data.codigo_suministro,
    data.nombre,
    data.apellidos,
    data.monto,
    data.aumento,
    data.porcentaje,
    data.interes, // Vacío (Columna L)
    data.tipo,
    data.monto_cuota,
    data.num_cuotas,
    data.capacidad_pago,
    data.estado,
    data.observacion
  ]);
  
  return ContentService.createTextOutput(JSON.stringify({"status": "success"})).setMimeType(ContentService.MimeType.JSON);
}
