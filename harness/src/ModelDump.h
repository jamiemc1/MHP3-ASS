#pragma once

// L1 fixtures for record behaviour that needs no search query: skill
// thresholds, decoration comparisons, charm validity, the my-charms file and
// charm comparisons under chosen "relevant" ability flags.
namespace ModelDump
{
	// mycharms_paths are synthetic my-charms files, each loaded as
	// CharmDatabase::LoadCustom would load Data/mycharms.txt.
	void Write( System::Collections::Generic::List< System::String^ >^ mycharms_paths, System::String^ out_path );
}
