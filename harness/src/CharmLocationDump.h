#pragma once

// L1 fixtures for the charm tooltip's logic: which charm tables can produce a
// charm, and how the tooltip reads a charm back from its display name.
namespace CharmLocationDump
{
	// Writes two sections:
	// - find_charm2: FindCharm2 (CharmDatabase.cpp:1006-1099) called directly
	//   for no ability, every ability at points 0-15, sampled two-skill pairs
	//   and their variations, and a few negative first points (unsigned wrap),
	//   each with all four slot counts where it applies
	// - parse_and_find: charm names passed to Utility::UpdateContextMenu
	//   (Common.cpp:157-230) with an empty cache, recording what it cached and
	//   the menu header, or the exception it threw. English (TeamHGG) names
	//   first, then a sample re-named in each other language, switching
	//   language in-process as the GUI's menu does (Form1.h:2031)
	void Write( System::String^ out_path );
}
