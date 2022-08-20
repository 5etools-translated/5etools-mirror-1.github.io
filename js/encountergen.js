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
		return {_sLevel: ent.minlvl ?? 0};
	}

	_getHash (ent) {
		return UrlUtil.encodeForHash([ent.name, ent.source, `${ent.minlvl ?? 0}-${ent.maxlvl ?? 0}`]);
	}

	_getHeaderId (ent) {
		return UrlUtil.encodeForHash([ent.name, ent.source]);
	}

	_getDisplayName (ent) {
		const ptHead = `${ent.name} Encounters`;
		if (ent.minlvl == null && ent.maxlvl == null) return ptHead;
		return `${ptHead} (Levels ${ent.minlvl}\u2013${ent.maxlvl})`;
	}
}

const encountersPage = new EncountersPage();
window.addEventListener("load", () => encountersPage.pOnLoad());
