#pragma once

// L1 fixtures: the game data and charm tables exactly as the legacy loaders
// hold them in memory, including list and dictionary enumeration order.
namespace DataDump
{
	// Abilities, skills, armour, decorations and materials, in the currently
	// loaded language.
	void WriteGameData( System::String^ out_path );

	// CharmDatabase::GenerateCharmTable() output: per-ability maximum points,
	// two-skill charm lists, table hash counts and the legal-charm hash list.
	void WriteCharmDatabase( System::String^ out_path );

	// Display names only, keyed by the language-independent indices. Used to
	// check each language file maps onto the same records.
	void WriteNames( System::String^ out_path );
}
