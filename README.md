# Sentinel Pi

Sentinel Pi is a Raspberry Pi 3 + CC1101 RF field console for authorised security testing, signal analysis, pulse capture, live RF visualisation, and hardware diagnostics.

## Highlights

- CC1101 hardware health check
- 433.92 MHz OOK/ASK monitoring
- GDO0 pulse-edge capture
- Full-screen RSSI graph and waterfall
- Automatic RF event/button-press detection
- Capture comparison and waveform viewer
- JSON / CSV / TXT export
- Synthetic Lab TX
- Wi-Fi / Bluetooth / Terminal / System tools
- GitHub Releases self-updater
- Backup before each software update

## Install

Download the latest Release ZIP, extract it, then:

```bash
chmod +x install.sh
sudo ./install.sh
sudo reboot
```

## Updates

Sentinel checks GitHub Releases from `Pragsi/sentinel`.

Each release should contain:

- `Sentinel_X.Y.Z.zip`
- `Sentinel_X.Y.Z.zip.sha256`

## Scope

For authorised RF testing, development, diagnostics, and signal analysis. Captured access-control signals are receive/analyse/export only. Lab TX uses a built-in synthetic test pattern.
