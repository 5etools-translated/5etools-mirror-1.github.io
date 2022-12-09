"use strict";

class PageFilterTrapsHazards extends PageFilter {
	// region static
	static sortFilterType (a, b) {
		return SortUtil.ascSortLower(Parser.trapHazTypeToFull(a.item), Parser.trapHazTypeToFull(b.item));
	}
	// endregion

	constructor () {
		super();

		this._typeFilter = new Filter({
			header: "Type",
			items: [
				"MECH",
				"MAG",
				"SMPL",
				"CMPX",
				"HAZ",
				"WTH",
				"ENV",
				"WLD",
				"GEN",
			],
			displayFn: Parser.trapHazTypeToFull,
			itemSortFn: PageFilterTrapsHazards.sortFilterType.bind(PageFilterTrapsHazards),
		});
	}

	static mutateForFilters (it) {
		it.trapHazType = it.trapHazType || "HAZ";
	}

	addToFilters (it, isExcluded) {
		if (isExcluded) return;

		this._sourceFilter.addItem(it.source);
		this._typeFilter.addItem(it.trapHazType);
	}

	async _pPopulateBoxOptions (opts) {
		opts.filters = [
			this._sourceFilter,
			this._typeFilter,
		];
	}

	toDisplay (values, it) {
		return this._filterBox.toDisplay(
			values,
			it.source,
			it.trapHazType,
		);
	}
}

class ListSyntaxTrapsHazards extends ListUiUtil.ListSyntax {
	_getSearchCacheStats (entity) {
		if (!entity.effect && !entity.trigger && !entity.countermeasures && !entity.entries) return "";
		const ptrOut = {_: ""};
		this._getSearchCache_handleEntryProp(entity, "effect", ptrOut);
		this._getSearchCache_handleEntryProp(entity, "trigger", ptrOut);
		this._getSearchCache_handleEntryProp(entity, "countermeasures", ptrOut);
		this._getSearchCache_handleEntryProp(entity, "entries", ptrOut);
		return ptrOut._;
	}
}
