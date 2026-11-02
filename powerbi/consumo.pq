let
    // Reemplazar por la URL HTTPS de la aplicación publicada. Sin secretos.
    BaseUrl = "https://REEMPLAZAR.onrender.com",
    FechaDesde = "2026-11-01",
    FechaHasta = "2026-11-30",
    Corte = DateTimeZone.ToText(DateTimeZone.FixedUtcNow(), "yyyy-MM-ddTHH:mm:ss.ffffffzzz", "en-US"),
    Page = (cursor as nullable text) as record =>
        let
            Params = [date_from=FechaDesde, date_to=FechaHasta, as_of=Corte, page_size="100"],
            Query = if cursor = null then Params else Record.AddField(Params,"after",cursor),
            Result = Json.Document(Web.Contents(BaseUrl, [RelativePath="api/v1/reports/usage", Query=Query, Headers=[Accept="application/json"], Timeout=#duration(0,0,2,0)]))
        in Result,
    Pages = List.Generate(() => Page(null), each _ <> null, each if [next_cursor] = null then null else Page([next_cursor]), each [items]),
    Rows = List.Combine(Pages),
    Columns = {"id","user_id","service","status","created_at","report_date","provider_calls","input_tokens","output_tokens","total_tokens"},
    Data = Table.FromRecords(Rows,Columns,MissingField.UseNull),
    Types = Table.TransformColumnTypes(Data,{{"user_id",Int64.Type},{"service",type text},{"status",type text},{"created_at",type datetimezone},{"report_date",type date},{"provider_calls",Int64.Type},{"input_tokens",Int64.Type},{"output_tokens",Int64.Type},{"total_tokens",Int64.Type}})
in
    Types
