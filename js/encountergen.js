"use strict";

class EncountersPage extends TableListPage {
	constructor () {
		super({
			dataSource: "data/encounters.json",

			dataProps: ["encounter"],
		});
	}

	static _COL_NAME_1 = "Encounter";

	static _FN_SORT (a, b, o) {
		if (o.sortBy === "name") return SortUtil.ascSort(a.data._sLevel, b.data._sLevel) || SortUtil.compareListNames(a, b);
		return 0;
	}

	_getListItemData (ent) {
		return {_sLevel: ent.minlvl};
	}

	_getHash (ent) {
		return UrlUtil.encodeForHash([ent.name, ent.source, `${ent.minlvl}-${ent.maxlvl}`]);
	}

	_getHeaderId (ent) {
		return UrlUtil.encodeForHash([ent.name, ent.source]);
	}

	_getDisplayName (ent) { return `${ent.name} Encounters (Levels ${ent.minlvl}\u2013${ent.maxlvl})`; }
}

const encountersPage = new EncountersPage();
window.addEventListener("load", () => encountersPage.pOnLoad());
