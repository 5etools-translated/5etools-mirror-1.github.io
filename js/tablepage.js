"use strict";

class TableListPage extends ListPage {
	constructor (...args) {
		super(...args);

		this._listMetas = {};
	}

	static _pad (number) {
		return String(number).padStart(2, "0");
	}

	_getHash (ent) { throw new Error(`Unimplemented!`); }
	_getHeaderId (ent) { throw new Error(`Unimplemented!`); }
	_getDisplayName (ent) { throw new Error(`Unimplemented!`); }

	get primaryLists () {
		return Object.values(this._listMetas).map(it => it.list);
	}

	static _FN_SORT; // Implement as required

	_getListItemData (ent, i) { return {}; }

	_addData (data) {
		const groups = data[this._dataProps[0]];
		this._dataList = groups
			.map(group => {
				return group.tables
					.map(tbl => {
						const out = MiscUtil.copy(group);
						delete out.tables;
						Object.assign(out, MiscUtil.copy(tbl));
						return out;
					});
			})
			.flat();

		const $wrpLists = $(`[data-name="tablepage-wrp-list"]`);

		for (let i = 0; i < this._dataList.length; i++) {
			const ent = this._dataList[i];

			const headerId = this._getHeaderId(ent);
			if (!this._listMetas[headerId]) {
				const $wrpList = $(`<div class="ve-flex-col w-100 list"></div>`);

				const isFirst = !Object.keys(this._listMetas).length;
				const list = this._initList({
					$iptSearch: $("#lst__search"),
					$wrpList,
					$btnReset: $("#reset"),
					$btnClear: $(`#lst__search-glass`),
					$dispPageTagline: isFirst ? $(`.page__subtitle`) : null,
					isBindFindHotkey: isFirst,
					optsList: {
						isUseJquery: true,
						fnSort: this.constructor._FN_SORT,
					},
				});

				const $dispShowHide = $(`<div class="lst__tgl-item-group mr-1">[\u2013]</div>`);

				const $btnHeader = $$`<div class="lst__item-group-header my-2 split-v-center" title="Source: ${Parser.sourceJsonToFull(ent.source)}">
					<div>${ent.name}</div>
					${$dispShowHide}
				</div>`
					.click(() => {
						$wrpList.toggleVe();
						if ($wrpList.hasClass("ve-hidden")) $dispShowHide.html(`[+]`);
						else $dispShowHide.html(`[\u2013]`);
					});

				list.on("updated", () => {
					$btnHeader.toggleVe(!!list.visibleItems.length);
				});

				$$`<div class="flex-col">
					${$btnHeader}
					${$wrpList}
				</div>`.appendTo($wrpLists);

				this._listMetas[headerId] = {
					list,
				};
			}

			const displayName = this._getDisplayName(ent);
			const hash = this._getHash(ent);

			const $ele = $$`<div class="lst__row ve-flex-col">
				<a href="#${hash}" class="lst--border lst__row-inner">${displayName}</a>
			</div>`;

			const listItem = new ListItem(
				i,
				$ele,
				displayName,
				{
					hash,
				},
				{
					...this._getListItemData(ent, i),
				},
			);

			this._listMetas[headerId].list.addItem(listItem);
		}
	}

	handleFilterChange () { /* No-op */ }
	async _pOnLoad_pInitPrimaryLists () { /* No-op */ }
	_pOnLoad_initVisibleItemsDisplay () { /* No-op */ }
	async _pOnLoad_pLoadListState () { /* No-op */ }
	_pOnLoad_bindMiscButtons () { /* No-op */ }
	pDoLoadSubHash () { /* No-op */ }

	_doLoadHash (id) {
		Renderer.get().setFirstSection(true);

		const ent = this._dataList[id];

		const table = ent.table;
		const tableName = this._getDisplayName(ent);
		const diceType = ent.diceType;

		const htmlRows = table.map(it => {
			const range = it.min === it.max ? this.constructor._pad(it.min) : `${this.constructor._pad(it.min)}-${this.constructor._pad(it.max)}`;
			return `<tr><td class="text-center p-0">${range}</td><td class="p-0">${Renderer.get().render(it.result)}</td></tr>`;
		});

		let htmlText = `
		<tr>
			<td colspan="6">
				<table class="w-100 stripe-odd-table">
					<caption>${tableName}</caption>
					<thead>
						<tr>
							<th class="col-2 text-center">
								<span class="roller" data-name="btn-roll">d${diceType}</span>
							</th>
							<th class="col-10">${this.constructor._COL_NAME_1}</th>
						</tr>
					</thead>
					<tbody>
						${htmlRows.join("")}
					</tbody>
				</table>
			</td>
		</tr>`;

		$("#pagecontent")
			.html(htmlText)
			.find(`[data-name="btn-roll"]`)
			.click(() => {
				this._roll(ent);
			})
			.mousedown(evt => {
				evt.preventDefault();
			});
	}

	_roll (ent) {
		const rollTable = ent.table;

		rollTable._rMax = rollTable._rMax == null
			? Math.max(...rollTable.filter(it => it.min != null).map(it => it.min), ...rollTable.filter(it => it.max != null).map(it => it.max))
			: rollTable._rMax;
		rollTable._rMin = rollTable._rMin == null
			? Math.min(...rollTable.filter(it => it.min != null).map(it => it.min), ...rollTable.filter(it => it.max != null).map(it => it.max))
			: rollTable._rMin;

		const roll = RollerUtil.randomise(rollTable._rMax, rollTable._rMin);

		let result;
		for (let i = 0; i < rollTable.length; i++) {
			const row = rollTable[i];
			const trueMin = row.max != null && row.max < row.min ? row.max : row.min;
			const trueMax = row.max != null && row.max > row.min ? row.max : row.min;
			if (roll >= trueMin && roll <= trueMax) {
				result = Renderer.get().render(row.result);
				break;
			}
		}

		// add dice results
		result = result.replace(RollerUtil.DICE_REGEX, (match) => {
			const r = Renderer.dice.parseRandomise2(match);
			return `<span class="roller" data-name="tablepage-reroll">${match}</span> (<span class="result">${r}</span>)`;
		});

		const $ele = $$`<span><strong>${this.constructor._pad(roll)}</strong> ${result}</span>`;

		$ele.find(`[data-name="tablepage-reroll"]`)
			.each((i, e) => {
				const $roller = $(e);
				$roller
					.click(() => {
						this._reroll($roller);
					})
					.mousedown(evt => {
						evt.preventDefault();
					});
			});

		Renderer.dice.addRoll({
			rolledBy: {
				name: this._getDisplayName(ent),
			},
			$ele,
		});
	}

	_reroll ($ele) {
		const resultRoll = Renderer.dice.parseRandomise2($ele.text());
		const $result = $ele.next(".result");
		const oldText = $result.text();
		$result.text(resultRoll);
		JqueryUtil.showCopiedEffect($result, oldText, true);
	}
}
