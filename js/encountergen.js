"use strict";

class EncountersPage extends TableListPage {
	constructor () {
		super({
			dataSource: "data/encounters.json",

			dataProps: ["encounter"],
		});
	}

	static _COL_NAME_1 = "Encounter";

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
