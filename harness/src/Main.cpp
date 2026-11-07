#include "stdafx.h"
#include "CharmDatabase.h"
#include "DataDump.h"
#include "LoadedData.h"
#include "SaveDump.h"
#include "SearchDump.h"

using namespace System;
using namespace System::Collections::Generic;

namespace
{
	int Usage()
	{
		Console::Error->WriteLine( L"Usage:" );
		Console::Error->WriteLine( L"  Harness dump-data    --out <file.json[.gz]> [--lang <language>] [--names-only] [--run-dir <dir>]" );
		Console::Error->WriteLine( L"  Harness dump-charms  --out <file.json[.gz]> [--lang <language>] [--run-dir <dir>]" );
		Console::Error->WriteLine( L"  Harness decrypt-save <save.bin> --out <file.json[.gz]> [--lang <language>] [--run-dir <dir>]" );
		Console::Error->WriteLine( L"  Harness search       <query.json> --out <prefix> [--run-dir <dir>]" );
		Console::Error->WriteLine( L"" );
		Console::Error->WriteLine( L"search writes <prefix>.manifest.json and <prefix>.solutions.txt.gz, in the query's language." );
		Console::Error->WriteLine( L"<language> is a folder name under Data/Languages, e.g. \"English (TeamHGG)\"." );
		Console::Error->WriteLine( L"Output ending in .gz is gzip-compressed." );
		Console::Error->WriteLine( L"--run-dir defaults to legacy/Run beside this harness." );
		return 2;
	}

	ref struct Options
	{
		String^ command;
		List< String^ >^ positional;
		String^ out_path;
		String^ language;
		String^ run_dir;
		bool names_only;

		Options() : positional( gcnew List< String^ > ), names_only( false ) {}
	};

	String^ OptionValue( array< String^ >^ args, int% i )
	{
		if( i + 1 >= args->Length )
			throw gcnew ArgumentException( L"Missing value for " + args[ i ] );
		return args[ ++i ];
	}

	Options^ Parse( array< String^ >^ args )
	{
		Options^ options = gcnew Options;
		for( int i = 0; i < args->Length; ++i )
		{
			String^ arg = args[ i ];
			if( arg == L"--out" )
				options->out_path = OptionValue( args, i );
			else if( arg == L"--lang" )
				options->language = OptionValue( args, i );
			else if( arg == L"--run-dir" )
				options->run_dir = OptionValue( args, i );
			else if( arg == L"--names-only" )
				options->names_only = true;
			else if( arg->StartsWith( L"--" ) )
				throw gcnew ArgumentException( L"Unknown option " + arg );
			else if( options->command == nullptr )
				options->command = arg;
			else
				options->positional->Add( arg );
		}
		return options;
	}

	String^ DefaultRunDir()
	{
		// harness/Release/Harness.exe -> legacy/Run
		String^ exe_dir = IO::Path::GetDirectoryName( Reflection::Assembly::GetExecutingAssembly()->Location );
		return IO::Path::GetFullPath( IO::Path::Combine( exe_dir, L"..", L"..", L"legacy", L"Run" ) );
	}

	// Same order as the GUI's constructor (Form1.h:309-322): load the data
	// files, build the charm tables, then apply the chosen language.
	void LoadGameData( Options^ options )
	{
		String^ run_dir = options->run_dir != nullptr ? IO::Path::GetFullPath( options->run_dir ) : DefaultRunDir();
		// The legacy loaders open "Data/..." relative to the working directory.
		IO::Directory::SetCurrentDirectory( run_dir );

		LoadedData^ data = gcnew LoadedData;
		data->ImportTextFiles();
		CharmDatabase::GenerateCharmTable();
		if( options->language != nullptr )
			StringTable::LoadLanguage( options->language );
	}
}

int main( array< String^ >^ args )
{
	Options^ options;
	try
	{
		options = Parse( args );
	}
	catch( ArgumentException^ error )
	{
		Console::Error->WriteLine( error->Message );
		return Usage();
	}
	if( options->command == nullptr || options->out_path == nullptr )
		return Usage();
	if( options->names_only && options->command != L"dump-data" )
	{
		Console::Error->WriteLine( L"--names-only only applies to dump-data" );
		return Usage();
	}
	if( options->command == L"search" && options->language != nullptr )
	{
		Console::Error->WriteLine( L"search takes its language from the query file; remove --lang" );
		return Usage();
	}

	// Resolve paths before LoadGameData changes the working directory.
	String^ out_path = IO::Path::GetFullPath( options->out_path );
	List< String^ >^ inputs = gcnew List< String^ >;
	for each( String^ path in options->positional )
		inputs->Add( IO::Path::GetFullPath( path ) );

	if( options->command == L"dump-data" && inputs->Count == 0 )
	{
		LoadGameData( options );
		if( options->names_only )
			DataDump::WriteNames( out_path );
		else
			DataDump::WriteGameData( out_path );
	}
	else if( options->command == L"dump-charms" && inputs->Count == 0 )
	{
		LoadGameData( options );
		DataDump::WriteCharmDatabase( out_path );
	}
	else if( options->command == L"decrypt-save" && inputs->Count == 1 )
	{
		LoadGameData( options );
		SaveDump::Write( inputs[ 0 ], out_path );
	}
	else if( options->command == L"search" && inputs->Count == 1 )
	{
		options->language = SearchDump::QueryLanguage( inputs[ 0 ] );
		LoadGameData( options );
		SearchDump::Run( inputs[ 0 ], out_path );
	}
	else
		return Usage();

	Console::WriteLine( L"Wrote " + out_path );
	return 0;
}
