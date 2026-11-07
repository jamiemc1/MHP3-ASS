#pragma once

namespace FixtureFiles
{
	// Writes text as UTF-8 without a BOM; gzip-compressed when the path ends in
	// ".gz". Every fixture goes through here so all files share one encoding.
	inline void WriteText( System::String^ path, System::String^ text )
	{
		array< System::Byte >^ bytes = ( gcnew System::Text::UTF8Encoding( false ) )->GetBytes( text );
		if( !path->EndsWith( L".gz" ) )
		{
			System::IO::File::WriteAllBytes( path, bytes );
			return;
		}
		System::IO::FileStream^ file = System::IO::File::Create( path );
		try
		{
			System::IO::Compression::GZipStream^ gzip =
				gcnew System::IO::Compression::GZipStream( file, System::IO::Compression::CompressionLevel::Optimal );
			try
			{
				gzip->Write( bytes, 0, bytes->Length );
			}
			finally
			{
				delete gzip;
			}
		}
		finally
		{
			delete file;
		}
	}
}

// Minimal JSON writer for harness output. Keys appear in the order the caller
// writes them and non-ASCII characters are \u-escaped, so the same input
// always produces byte-identical output.
ref class JsonWriter
{
public:
	JsonWriter()
		: sb( gcnew System::Text::StringBuilder ),
		  first_in_container( gcnew System::Collections::Generic::Stack< bool > ),
		  depth( 0 ),
		  after_key( false )
	{}

	void BeginObject() { BeforeValue(); sb->Append( L'{' ); Open(); }
	void EndObject() { Close( L'}' ); }
	void BeginArray() { BeforeValue(); sb->Append( L'[' ); Open(); }
	void EndArray() { Close( L']' ); }

	void Key( System::String^ key )
	{
		BeforeElement();
		WriteString( key );
		sb->Append( L": " );
		after_key = true;
	}

	void Value( System::String^ value )
	{
		BeforeValue();
		if( value == nullptr )
			sb->Append( L"null" );
		else
			WriteString( value );
	}

	void Value( int value ) { BeforeValue(); sb->Append( value ); }
	void Value( unsigned value ) { BeforeValue(); sb->Append( value ); }
	void Value( long long value ) { BeforeValue(); sb->Append( value ); }
	void Value( bool value ) { BeforeValue(); sb->Append( value ? L"true" : L"false" ); }
	void Null() { BeforeValue(); sb->Append( L"null" ); }

	void Field( System::String^ key, System::String^ value ) { Key( key ); Value( value ); }
	void Field( System::String^ key, int value ) { Key( key ); Value( value ); }
	void Field( System::String^ key, unsigned value ) { Key( key ); Value( value ); }
	void Field( System::String^ key, long long value ) { Key( key ); Value( value ); }
	void Field( System::String^ key, bool value ) { Key( key ); Value( value ); }

	virtual System::String^ ToString() override
	{
		return sb->ToString() + L"\n";
	}

	void WriteToFile( System::String^ path )
	{
		FixtureFiles::WriteText( path, ToString() );
	}

private:
	System::Text::StringBuilder^ sb;
	System::Collections::Generic::Stack< bool >^ first_in_container;
	int depth;
	bool after_key;

	void BeforeValue()
	{
		if( after_key )
		{
			after_key = false;
			return;
		}
		BeforeElement();
	}

	void BeforeElement()
	{
		if( first_in_container->Count == 0 )
			return;
		if( first_in_container->Peek() )
		{
			first_in_container->Pop();
			first_in_container->Push( false );
		}
		else
			sb->Append( L',' );
		NewLine();
	}

	void Open()
	{
		first_in_container->Push( true );
		depth++;
	}

	void Close( wchar_t bracket )
	{
		const bool was_empty = first_in_container->Pop();
		depth--;
		if( !was_empty )
			NewLine();
		sb->Append( bracket );
	}

	void NewLine()
	{
		sb->Append( L'\n' );
		sb->Append( L' ', depth * 2 );
	}

	void WriteString( System::String^ text )
	{
		sb->Append( L'"' );
		for each( wchar_t c in text )
		{
			if( c == L'"' )
				sb->Append( L"\\\"" );
			else if( c == L'\\' )
				sb->Append( L"\\\\" );
			else if( c == L'\n' )
				sb->Append( L"\\n" );
			else if( c == L'\r' )
				sb->Append( L"\\r" );
			else if( c == L'\t' )
				sb->Append( L"\\t" );
			else if( c < 0x20 || c > 0x7e )
				sb->Append( L"\\u" )->Append( ( (int)c ).ToString( L"x4" ) );
			else
				sb->Append( c );
		}
		sb->Append( L'"' );
	}
};
