#pragma once

// settings.cfg and .ass fixtures: the solution part of Form1::SaveConfig and
// Form1::LoadConfig (Form1.h:342-379, :430-435, :495-539), with the result
// lists and de-duplication set of Form1. File > Save and File > Load (.ass)
// call the same two functions with another path (Form1.h:2289-2312). The
// header lines (options, skill rows) are not covered.
namespace ResultsDump
{
	// Runs a corpus query's search, then writes a JSON fixture of three steps:
	// "save" (the solution text SaveConfig writes after the search), "load"
	// (that text read back by a fresh GUI, as at start-up) and
	// "load_after_search" (read back by the GUI that ran the search, whose
	// de-duplication set LoadConfig doesn't clear).
	void RunSearch( System::String^ query_path, System::String^ out_path );

	// Reads the solutions of a settings.cfg or .ass file into a fresh GUI, in
	// the language its header names, and writes a JSON fixture of one "load" step.
	void RunFile( System::String^ cfg_path, System::String^ out_path );
}
