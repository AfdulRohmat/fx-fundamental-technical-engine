#property copyright "Research-only; no trading operations"
#property version   "1.00"
#property script_show_inputs

input datetime InpFrom = D'2017.01.01 00:00:00';
input string InpCurrencies = "USD,EUR,GBP,JPY,AUD,CAD";
input string InpOutputDirectory = "fx-fundamental-technical-engine";

string ValueText(const long raw_value, const uint digits)
  {
   if(raw_value == LONG_MIN)
      return "";
   return DoubleToString((double)raw_value / 1000000.0, (int)digits);
  }

string CleanToken(string value)
  {
   StringTrimLeft(value);
   StringTrimRight(value);
   StringToUpper(value);
   return value;
  }

string CleanField(string value)
  {
   StringReplace(value, "\t", " ");
   StringReplace(value, "\r", " ");
   StringReplace(value, "\n", " ");
   return value;
  }

string MetadataCurrencies()
  {
   string value = InpCurrencies;
   StringReplace(value, ",", ";");
   return value;
  }

void WriteMetadata(const string filename,
                   const datetime exported_at,
                   const int offset_seconds,
                   const int row_count,
                   const int failure_count)
  {
   int handle = FileOpen(filename,
                         FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON,
                         '\t',
                         CP_UTF8);
   if(handle == INVALID_HANDLE)
     {
      PrintFormat("CALENDAR_EXPORT_META_OPEN_FAILED error=%d", GetLastError());
      return;
     }
   FileWrite(handle,
             "schema_version",
             "exported_at_server",
             "server_utc_offset_seconds_at_export",
             "from_server",
             "to_server",
             "currencies",
             "row_count",
             "failure_count");
   FileWrite(handle,
             "1.0",
             TimeToString(exported_at, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
             offset_seconds,
             TimeToString(InpFrom, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
             TimeToString(exported_at, TIME_DATE | TIME_MINUTES | TIME_SECONDS),
             MetadataCurrencies(),
             row_count,
             failure_count);
   FileFlush(handle);
   FileClose(handle);
  }

void OnStart()
  {
   const datetime exported_at = TimeTradeServer();
   const int offset_seconds = (int)(TimeTradeServer() - TimeGMT());
   const string output_file = InpOutputDirectory + "\\calendar_export.tsv";
   const string metadata_file = InpOutputDirectory + "\\calendar_export_meta.tsv";

   FolderCreate(InpOutputDirectory, FILE_COMMON);
   int handle = FileOpen(output_file,
                         FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON,
                         '\t',
                         CP_UTF8);
   if(handle == INVALID_HANDLE)
     {
      PrintFormat("CALENDAR_EXPORT_OPEN_FAILED error=%d", GetLastError());
      return;
     }

   FileWrite(handle,
             "schema_version",
             "value_id",
             "event_id",
             "release_time_server",
             "release_epoch_raw",
             "reference_period_server",
             "reference_epoch_raw",
             "revision",
             "actual",
             "forecast",
             "previous_as_reported",
             "revised_previous",
             "impact_type",
             "country_id",
             "country_code",
             "country_name",
             "currency",
             "event_code",
             "event_name",
             "event_type",
             "sector",
             "frequency",
             "time_mode",
             "unit",
             "importance",
             "multiplier",
             "digits",
             "source_url",
             "server_utc_offset_seconds_at_export");

   string currencies[];
   const int currency_count = StringSplit(InpCurrencies, ',', currencies);
   int rows = 0;
   int failures = 0;

   for(int currency_index = 0; currency_index < currency_count; currency_index++)
     {
      const string currency = CleanToken(currencies[currency_index]);
      if(StringLen(currency) == 0)
         continue;

      MqlCalendarValue values[];
      ResetLastError();
      const int value_count = CalendarValueHistory(values,
                                                   InpFrom,
                                                   exported_at,
                                                   "",
                                                   currency);
      if(value_count < 0)
        {
         failures++;
         PrintFormat("CALENDAR_EXPORT_QUERY_FAILED currency=%s error=%d",
                     currency,
                     GetLastError());
         continue;
        }

      for(int value_index = 0; value_index < value_count; value_index++)
        {
         const MqlCalendarValue value = values[value_index];
         MqlCalendarEvent event;
         MqlCalendarCountry country;
         if(!CalendarEventById(value.event_id, event))
           {
            failures++;
            continue;
           }
         if(!CalendarCountryById(event.country_id, country))
           {
            failures++;
            continue;
           }

         FileWrite(handle,
                   "1.0",
                   value.id,
                   value.event_id,
                   TimeToString(value.time,
                                TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                   (long)value.time,
                   TimeToString(value.period,
                                TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                   (long)value.period,
                   value.revision,
                   ValueText(value.actual_value, event.digits),
                   ValueText(value.forecast_value, event.digits),
                   ValueText(value.prev_value, event.digits),
                   ValueText(value.revised_prev_value, event.digits),
                   (int)value.impact_type,
                   event.country_id,
                   CleanField(country.code),
                   CleanField(country.name),
                   CleanField(country.currency),
                   CleanField(event.event_code),
                   CleanField(event.name),
                   (int)event.type,
                   (int)event.sector,
                   (int)event.frequency,
                   (int)event.time_mode,
                   (int)event.unit,
                   (int)event.importance,
                   (int)event.multiplier,
                   event.digits,
                   CleanField(event.source_url),
                   offset_seconds);
         rows++;
        }
     }

   FileFlush(handle);
   FileClose(handle);
   WriteMetadata(metadata_file, exported_at, offset_seconds, rows, failures);
   PrintFormat("CALENDAR_EXPORT_COMPLETE rows=%d failures=%d output=%s",
               rows,
               failures,
               output_file);
  }
