# DBZ: Attack of the Saiyans Randomizer by Momentum DevTools
![UI Showcase](ui_showcase.png)

### Info
This project was created to fully randomize the Nintendo DS classic *Dragon Ball Z: Attack of the Saiyans* (2009). Built by reverse-engineering the ARM9 binary and extracting the proprietary `.narc` file system, this tool allows for complete procedural manipulation of encounters, stats, items, and boss logic.

Have a look at the [Release page](https://github.com/momentumdevtools/dbz-aots-randomizer/releases) for changelogs and downloads. 

*Legal Disclaimer: This tool does not provide any copyrighted material. You must supply your own legally dumped `.nds` ROM of the game to use this software.*

### Contributing
If you want to contribute something to the codebase (e.g., expanding Archipelago logic or new hex-mapping), we'd recommend creating an issue for it first. This way, we can discuss whether or not it's a good fit for the randomizer before you put in the work to implement it. This is just to save you time in the event that we don't think it's something we want to accept.

### What is a good fit for the randomizer?
In general, we try to make settings as universal as possible. This means that it preferably should work without consistently breaking the game's core progression (preventing softlocks), and also that it's something many people will find useful. If the setting is very niche, it will mostly just bloat the GUI. 

If your idea is a change to an existing setting rather than a new setting, it needs to be well motivated.

### Feature requests
We do not take feature requests. *(Note: Patrons have voting rights on major architectural milestones, but individual feature requests on GitHub will be closed).*

### Bug reports
If you encounter something that seems to be a bug (e.g., a specific seed causing a crash or softlock), submit an issue using the Issue tracker. Please always include your Seed, your exact GUI settings, and the emulator you are using.

### Other problems
If you have problems using the randomizer, it could be because of a bad ROM dump, a strict Antivirus blocking the `.exe`, or your operating system. Ensure your base ROM is a clean, unmodified dump of the game before creating an issue.

### Support the Development
If you want to support our reverse-engineering efforts, read our technical Ghidra dev-logs, or get early access to beta builds, check out our [Patreon](https://www.patreon.com/momentumdevtools/).