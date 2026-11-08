#pragma once

// L3 fixtures: a full Quick Search, following Form1.h's FormulateQuery,
// StartSearch, DoWork and result de-duplication without the UI. Workers run
// one at a time in the order the GUI starts them.
namespace SearchDump
{
	// Reads a corpus query (JSON) and writes <out_prefix>.manifest.json and
	// <out_prefix>.solutions.txt.gz. Solution lines use the GUI's settings.cfg
	// format (Form1.h:495-538), in the order the GUI would add them. The
	// manifest records SHA-256 hashes of the uncompressed lines: in order, as
	// a sorted set, and per worker for the lines it added.
	// With write_candidates, also writes <out_prefix>.candidates.txt.gz: every
	// solution each worker found before duplicate removal, as
	// "<worker>\t<charm name>\t<solution line>". The GUI keeps a subset of
	// these that depends on thread timing, so this is how a GUI result is
	// checked against the harness when the two kept different duplicates.
	// With max_solution_lines >= 0, the solutions file is written only for at
	// most that many lines (the manifest says whether it was). With
	// record_exceptions, a worker that throws ends the query and the manifest
	// records the exception instead of the harness failing.
	void Run( System::String^ query_path, System::String^ out_prefix, const bool write_candidates,
			  const int max_solution_lines, const bool record_exceptions );
}
