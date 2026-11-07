# Quirks of the original

Behaviour of `legacy/` that looks unintended but which the port reproduces
for parity. Each entry cites the original source and the golden fixture that
demonstrates it. Revisit once the differential-fuzz phase passes.

| # | Behaviour | Original | Fixture | Decision |
|---|---|---|---|---|
| 1 | `EqualAbilities` compares `l2[i]->amount != l2[i]->amount` (always false), so charm comparisons built on it ignore point amounts: `BasicallyTheSameAs` (used by "my charms" mode's `AddCharmToOptimalList`) and `operator==` | `Armor.cpp:290-305` | `search/1a-*`; save import | Reproduce |
| 2 | `Charm` has a member `operator==`, so `a == b` on two `Charm^` handles is a value comparison (with quirk 1's amount blindness), not a reference comparison. "Select Best" on import (`current_charms[ i ] == current_charms[ j ]`) relies on it | `Armor.cpp:300-305`, `ImportCharms.h:360-361` | Save import (harness output matches the GUI's `mycharms.txt`) | Reproduce |
| 3 | Import always replaces the existing charm list: `btnOK_Click` tests `if( chkDeleteExisting )`, the check box handle (never null), not its `Checked` state | `ImportCharms.h:298-299` | Save import | Reproduce; the port's import replaces the list |
| 4 | Duplicate removal keys charmed solutions on charm name plus an armour "hash" `sum(index << (slot * 3))`. Armour indices exceed 200, so the shifted values overlap and two different armour sets can collide; the later one is silently dropped. Charm-free solutions are never de-duplicated | `Form1.h:1691-1745` | `search/1a-*` (53,688 found, 52,812 kept) | Reproduce |
| 5 | Which of two colliding solutions survives depends on which search thread reports first. The harness searches single-threaded in `StartSearch` order, and the port follows that order. Query 1b gives the same set as the GUI despite the GUI's different order | `Form1.h:1225-1375`, `:1732-1746` | `search/1a-*`; query 1b vs GUI | Reproduce the single-threaded order |
