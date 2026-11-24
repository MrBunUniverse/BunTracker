# Bun Tracker

Bun Tracker is my own take on [SlimeVR Server](https://github.com/SlimeVR/SlimeVR-Server), the open-source software that turns body trackers into full-body tracking for VR. I play VRChat with trackers on a Mac and wanted the software to fit my setup, so I started changing things. I share it with friends and a few people I trust.

**Heads up: this is an early work in progress.** Stuff is unfinished and changes often, and I've only tested it on macOS. It's an unofficial fork. It is not a SlimeVR release, and it is not affiliated with the SlimeVR team.

## What's different from SlimeVR

### The desktop app

- A redesigned interface with a top navigation bar, in navy, gray and amber.
- Tracker cards instead of plain rows. They adapt to the window width.
- Three themes: Bun, Fox and Dog. Pick your animal.
- A microphone picker for the voice features.
- A User Agreement page built in, under Settings.

### Tracking

- Drift compensation keeps trackers aligned through long sessions. The settings are adjustable, and you can switch it on for all trackers at once.
- Resets know about your posture. There's even a yaw reset for when you're lying down.
- A tracker that drops out can rejoin more smoothly instead of snapping back.
- An automatic full reset option.
- A foot-slide clamp, so your feet slide across the floor less.
- A stability estimate for each tracker, plus smoother handling of uneven network timing.

### Hardware

- An ESP32 USB dongle works as a tracker receiver.
- Trackers can be updated over the air through the dongle, including a Wi-Fi flash mode. No need to open them up.

### VRChat and Meta Quest

- VRChat chatbox tools: show what's playing in Apple Music, a BPM readout, and voice dictation straight into the chatbox.
- A remote page that controls the separate Quest StreamCast app.

### Privacy

- No error reports or usage data go to SlimeVR, and the app doesn't check upstream for updates.

## Not done yet

- Windows and Linux are untested. They might work. They might not.
- No installers yet.
- A few native features are switched off for now: the system tray, Mac built-in dictation, and Discord presence. The app tells you when one is unavailable.

Developer notes live in [`docs/`](docs/README.md). Every change is listed in the [changelog](CHANGELOG.md).

## User Agreement

This is the same text as in the app under Settings > User Agreement.

**About Bun Tracker.** Bun Tracker is my personal version of SlimeVR Server, adapted for my own setup and shared with friends and a few people I trust. It's an unofficial project. SlimeVR and its developers didn't make it, don't support it, and aren't connected to it in any way. Bun Tracker is an unofficial fork of SlimeVR Server and is not affiliated with, endorsed by, or sponsored by SlimeVR, Meta Platforms, VRChat, Valve, Apple, or Espressif. All trademarks belong to their respective owners.

**Credit where it's due.** SlimeVR Server is the work of the SlimeVR team and its many contributors, and nearly everything here is built on what they made. I don't claim their work as my own. All credit for the original project belongs to them, and its Apache 2.0 and MIT licenses and copyright notices still apply.

**If something goes wrong.** Please don't take problems with Bun Tracker to the SlimeVR developers, their Discord, or their GitHub. Many of the changes in this version are mine, so an issue you run into may not exist in SlimeVR at all. Message me on Discord instead.

**AI-assisted ("vibe coding").** Much of Bun Tracker's own code and docs (the changes on top of SlimeVR) was written with help from AI coding assistants, a way of working often called "vibe coding". I direct the work, test it on my own setup and review what goes in, but I'm not a professional software developer, and the code hasn't been through a professional or SlimeVR review. So it may contain bugs, odd behavior or mistakes that a careful human review would have caught, and you should treat it as experimental. Please don't rely on it where a tracking error could hurt you or others, and play in a safe, clear space. The original SlimeVR code it builds on was written by the SlimeVR team, not by AI. AI involvement applies only to my changes, and SlimeVR's Apache 2.0 and MIT licenses and copyright notices still apply. The Mr Bun character and pose illustrations are my own character; the current illustrations are AI-generated placeholders (made with an image model from my character photo, using upstream images only as pose references) to be replaced with commissioned art. The Mr Bun character and artwork are © MrBunUniverse, all rights reserved, and are not covered by the MIT or Apache 2.0 licenses of the code.

**No guarantees.** I look after Bun Tracker in my spare time and share it as-is, without any warranty. I'll do my best to help when something breaks, but please use it at your own risk.

**In short.** By using Bun Tracker, you agree to the points above, including that parts of it are AI-assisted and provided as-is, and to treat the original SlimeVR developers with the respect their work deserves. Nothing in this agreement restricts any rights granted by the Apache 2.0 or MIT licenses. Thank you for using it.

## Contact

Got a problem or a question? Find me on Discord: `jamevm` (SirJame). [Open my profile](https://discord.com/users/390812634481688576), or search "jamevm" in Discord's Add Friend.

## License

Based on the work of the [SlimeVR](https://slimevr.dev) project and its contributors ([SlimeVR-Server](https://github.com/SlimeVR/SlimeVR-Server)). SlimeVR is a trademark of its owners; see [docs/TRADEMARK.md](docs/TRADEMARK.md).

This fork's own modifications are dual-licensed under the MIT License ([`docs/licenses/LICENSE-MIT`](docs/licenses/LICENSE-MIT)) or the Apache License, Version 2.0 ([`LICENSE`](LICENSE)), at your option, the same as upstream SlimeVR Server. Existing upstream code in `server/` is MIT-only; new contributions are dual-licensed under both MIT and Apache 2.0. Details are in [`NOTICE`](NOTICE), [`docs/licenses/`](docs/licenses), and [`server/LICENSE.md`](server/LICENSE.md).
