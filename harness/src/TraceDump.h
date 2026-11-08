#pragma once

// L2 fixtures: Solution::MatchesQuery (Solution.cpp:660-724) stage by stage,
// for sampled armour combinations of a query, rejected ones included.
namespace TraceDump
{
	// The query file a trace spec names, resolved against the spec's directory.
	System::String^ QueryPath( System::String^ spec_path );

	// Reads a trace spec (JSON: "query", optional "stride" and "include") and
	// writes <out_path> as JSON lines: a header (the query echo, workers,
	// per-worker census over every combination, rel_decoration_map, point_score
	// ranks after the run), then one line per sampled combination with its
	// stages. Every combination runs twice: through the real MatchesQuery and
	// through a stepped copy of it, and the harness throws if the two end in
	// different states, so the copy can't drift from the original.
	void Run( System::String^ spec_path, System::String^ out_path );
}
