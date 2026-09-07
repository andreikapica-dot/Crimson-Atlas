const fs = require('fs');
const path = require('path');

module.exports = async function(context) {
    const localeDir = path.join(context.appOutDir, 'locales');
    if (!fs.existsSync(localeDir)) return;

    const keep = ['en-US.pak', 'en-GB.pak', 'ru.pak'];
    const removed = [];
    for (const file of fs.readdirSync(localeDir)) {
        if (!keep.includes(file)) {
            fs.unlinkSync(path.join(localeDir, file));
            removed.push(file);
        }
    }
    console.log(`afterPack: removed ${removed.length} unnecessary locale files (kept: ${keep.join(', ')})`);
};
