#pragma once

// L2 fixtures: what Form1::FormulateQuery sets up before a search starts.
namespace RelevanceDump
{
	// Reads a corpus query (JSON) and writes LoadedData::GetRelevantData's
	// result (relevant abilities, relevant and inferior armour per slot and
	// decorations, each armour piece's no_skills and danger) and
	// CharmDatabase::GetCharms for one- and two-skill charms. Charm fields in
	// the query are ignored: none of this reads the my-charms list.
	void Run( System::String^ query_path, System::String^ out_path );

	// Decoration::GetBestDecoration( ability, max_slots, query ), Decoration.cpp:104-124,
	// for every ability, max slots 0-3 and the GUI's HR and village ranges
	// (1-6 each, Form1.h:655-709). It reads nothing else from the query.
	void WriteBestDecorations( System::String^ out_path );
}
