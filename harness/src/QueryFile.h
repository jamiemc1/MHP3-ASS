#pragma once

ref struct Query;
ref class LoadedData;

// Corpus query files (JSON), shared by every command that builds a Query.
namespace QueryFile
{
	typedef System::Collections::Generic::Dictionary< System::String^, System::Object^ > JsonObject;

	JsonObject^ Read( System::String^ path );

	// The query as read, for goldens to echo so tests can tell when the file
	// changed after the golden was generated.
	System::String^ Serialize( JsonObject^ spec );

	// The Data/Languages folder the query was written for. Charm names depend on it.
	System::String^ Language( System::String^ path );

	int GetInt( JsonObject^ spec, System::String^ key );
	bool GetBool( JsonObject^ spec, System::String^ key );
	System::String^ GetString( JsonObject^ spec, System::String^ key );
	array< System::Object^ >^ GetArray( JsonObject^ spec, System::String^ key );

	// Form1::FormulateQuery( false, use_gunner_skills ), Form1.h:1184-1216, with
	// the form's controls replaced by corpus fields. Ends with
	// LoadedData::GetRelevantData, as the original does.
	Query^ FormulateQuery( LoadedData^ data, JsonObject^ spec );
}
