"use strict";

function handleFail () {
	console.error("Tests failed!");
	process.exit(1);
}

async function main () {
	if (!(await require("./test-tags"))) handleFail();
	if (!(await require("./test-images"))) handleFail();
	await require("./test-pagenumbers"); // don't fail on missing page numbers
	if (!(await require("./test-json"))) handleFail();
	if (!(await require("./test-misc"))) handleFail();
	if (!(await require("./test-multisource.js"))) handleFail();
	if (!(await require("./test-language-fonts.js"))) handleFail();
	if (!(await require("./test-foundry.js"))) handleFail();
	process.exit(0);
}

main()
	.then(() => console.log("Tests complete."))
	.catch(e => {
		console.error(e);
		throw e;
	});
