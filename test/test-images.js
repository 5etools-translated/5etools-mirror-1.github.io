import * as fs from "fs";
import "../js/parser.js";
import "../js/utils.js";
import * as ut from "../node/util.js";

class _TestTokenImages {
	static _IS_CLEAN_MM_EXTRAS = false;

	static expected = new Set();
	static expectedDirs = {};
	static existing = new Set();
	static expectedFromHashToken = {};

	static _mmTokens = null;

	static _isMmToken (filename) {
		if (!this._mmTokens) this._mmTokens = fs.readdirSync("./img/MM").mergeMap(it => ({[it]: true}));
		return !!this._mmTokens[filename.split("/").last()];
	}

	// Loop through each bestiary-related img directory and push the list of files in each.
	static run () {
		console.log(`##### Reconciling the PNG tokens against the bestiary JSON #####`);

		// Loop through each bestiary JSON file push the list of expected PNG files.
		fs.readdirSync("./data/bestiary")
			.filter(file => file.startsWith("bestiary") && file.endsWith(".json"))
			.forEach(file => {
				const result = JSON.parse(fs.readFileSync(`./data/bestiary/${file}`));
				result.monster.forEach(m => {
					const source = Parser.sourceJsonToAbv(m.source);
					const implicitTokenPath = `${source}/${Parser.nameToTokenName(m.name)}.png`;

					if (m.hasToken) this.expectedFromHashToken[implicitTokenPath] = true;

					if (fs.existsSync(`./img/${source}`)) {
						this.expected.add(implicitTokenPath);

						// add tokens specified as part of variants
						if (m.variant) {
							m.variant.filter(it => it.token).forEach(entry => this.expected.add(`${Parser.sourceJsonToAbv(entry.token.source)}/${Parser.nameToTokenName(entry.token.name)}.png`));
						}

						// add tokens specified as alt art
						if (m.altArt) {
							m.altArt.forEach(alt => this.expected.add(`${Parser.sourceJsonToAbv(alt.source)}/${Parser.nameToTokenName(alt.name)}.png`));
						}
					} else this.expectedDirs[source] = true;
				});
			});

		const IGNORED_PREFIXES = [
			".",
			"_",
		];

		const IGNORED_EXTENSIONS = [
			".git",
			".gitignore",
			".png",
			".txt",
		];

		const IGNORED_DIRS = new Set([
			"adventure",
			"backgrounds",
			"dmscreen",
			"deities",
			"variantrules",
			"rules",
			"objects",
			"bestiary",
			"book",
			"items",
			"races",
			"vehicles",
			"characters",
			"conditionsdiseases",
			"languages",
			"plutonium",
			"covers",
			"spells",
			"charcreationoptions",
			"recipes",
			"feats",
			"decks",
			"traps",
		]);

		fs.readdirSync("./img")
			.filter(file => !(IGNORED_PREFIXES.some(it => file.startsWith(it) || IGNORED_EXTENSIONS.some(it => file.endsWith(it)))))
			.forEach(dir => {
				if (!IGNORED_DIRS.has(dir)) {
					fs.readdirSync(`./img/${dir}`).forEach(file => {
						this.existing.add(`${dir.replace("(", "").replace(")", "")}/${file}`);
					});
				}
			});

		let isError = false;
		const results = [];
		this.expected.forEach((img) => {
			if (!this.existing.has(img)) results.push(`[ MISSING] ${img}`);
		});
		this.existing.forEach((img) => {
			delete this.expectedFromHashToken[img];
			if (!this.expected.has(img)) {
				if (this._IS_CLEAN_MM_EXTRAS && this._isMmToken(img)) {
					fs.unlinkSync(`./img/${img}`);
					results.push(`[ !DELETE] ${img}`);
					return;
				}
				results.push(`[   EXTRA] ${img}`);
				isError = true;
			}
		});

		Object.keys(this.expectedDirs).forEach(k => results.push(`Directory ${k} doesn't exist!`));
		results
			.sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))
			.forEach((img) => console.warn(img));

		if (Object.keys(this.expectedFromHashToken).length) console.warn(`Declared in Bestiary data but not found:`);
		Object.keys(this.expectedFromHashToken).forEach(img => console.warn(`[MISMATCH] ${img}`));

		if (!this.expected.size && !Object.keys(this.expectedFromHashToken).length) console.log("Tokens are as expected.");

		return isError;
	}
}

class _TestAdventureBookImages {
	static run () {
		const pathsMissing = [];

		const walker = MiscUtil.getWalker({isNoModification: true});

		const getHandler = (filename, out) => {
			const checkHref = (href) => {
				if (href?.type !== "internal") return;
				if (fs.existsSync(`./img/${href.path}`)) return;
				out.push(`${filename} :: ${href.path}`);
			};

			return (obj) => {
				if (obj.type !== "image") return;
				checkHref(obj.href);
				checkHref(obj.hrefThumbnail);
			};
		};

		[
			{filename: "adventures.json", prop: "adventure", dir: "adventure"},
			{filename: "books.json", prop: "book", dir: "book"},
		].flatMap(({filename, prop, dir}) => ut.readJson(`./data/${filename}`)[prop]
			.map(({id}) => `./data/${dir}/${dir}-${id.toLowerCase()}.json`))
			.forEach(filename => {
				walker.walk(
					ut.readJson(filename),
					{
						object: getHandler(filename, pathsMissing),
					},
				);
			});

		if (pathsMissing.length) {
			console.log(`Adventure/Book Errors:\n${pathsMissing.map(it => `\t${it}`).join("\n")}`);
			return true;
		}

		console.log(`##### Adventure/Book Image Tests Passed #####`);
		return false;
	}
}

function main () {
	if (!fs.existsSync("./img")) return true;

	if (_TestTokenImages.run()) return false;
	if (_TestAdventureBookImages.run()) return false;

	return true;
}

export default main();
