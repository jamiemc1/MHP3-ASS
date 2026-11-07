#pragma once

// L3 fixtures: a full Quick Search, following Form1.h's FormulateQuery,
// StartSearch, DoWork and result de-duplication without the UI. Workers run
// one at a time in the order the GUI starts them.
namespace SearchDump
{
	// The Data/Languages folder the query was written for. Charm names, and so
	// duplicate removal, depend on it.
	System::String^ QueryLanguage( System::String^ query_path );

	// Reads a corpus query (JSON) and writes <out_prefix>.manifest.json and
	// <out_prefix>.solutions.txt.gz. Solution lines use the GUI's settings.cfg
	// format (Form1.h:495-538), in the order the GUI would add them.
	// With write_candidates, also writes <out_prefix>.candidates.txt.gz: every
	// solution each worker found before duplicate removal, as
	// "<worker>\t<charm name>\t<solution line>". The GUI keeps a subset of
	// these that depends on thread timing, so this is how a GUI result is
	// checked against the harness when the two kept different duplicates.
	void Run( System::String^ query_path, System::String^ out_prefix, bool write_candidates );
}
