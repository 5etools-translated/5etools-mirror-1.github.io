"use strict";

class PageFilterTables extends PageFilter {
	// region static
	static _sourceSelFn (val) {
		return !SourceUtil.isNonstandardSource(val) && !SourceUtil.isAdventure(val);
	}
	// endregion

	constructor () {
		super({sourceFilterOpts: {selFn: PageFilterTables._sourceSelFn}});

		this._miscFilter = new Filter({header: "Miscellaneous", items: ["SRD", "Basic Rules"], isMiscFilter: true});
	}

	static mutateForFilters (it) {
		it._fMisc = it.srd ? ["SRD"] : [];
		if (it.basicRules) it._fMisc.push("Basic Rules");
	}

	addToFilters (it, isExcluded) {
		if (isExcluded) return;

		this._sourceFilter.addItem(it.source);
	}

	async _pPopulateBoxOptions (opts) {
		opts.filters = [
			this._sourceFilter,
			this._miscFilter,
		];
	}

	toDisplay (values, it) {
		return this._filterBox.toDisplay(
			values,
			it.source,
			it._fMisc,
		);
	}
}

class ListSyntaxTables extends ListUiUtil.ListSyntax {
	_getSearchCacheStats (entity) {
		if (!entity.rows && !entity.tables) return "";
		const ptrOut = {_: ""};
		this._getSearchCache_handleEntryProp(entity, "rows", ptrOut);
		this._getSearchCache_handleEntryProp(entity, "tables", ptrOut);
		return ptrOut._;
	}
}
