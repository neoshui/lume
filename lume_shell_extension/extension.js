/* Lume Clipboard Bridge — runs inside GNOME Shell, not as a normal client. */
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const MAX_ENTRIES = 200;

export default class LumeClipboardBridge extends Extension {
    enable() {
        this._dataDir = GLib.build_filenamev([GLib.get_user_data_dir(), 'lume', 'shell_clipboard']);
        this._imagesDir = GLib.build_filenamev([this._dataDir, 'images']);
        // make_directory_with_parents() throws FILE_EXISTS on every later
        // enable.  An extension may be re-enabled repeatedly by GNOME, so
        // only create this persistent directory on its first run.
        const imagesDir = Gio.File.new_for_path(this._imagesDir);
        if (!imagesDir.query_exists(null))
            imagesDir.make_directory_with_parents(null);
        this._clipboard = St.Clipboard.get_default();
        // Use the Shell singleton rather than the legacy global variable so
        // this keeps working across recent GNOME Shell releases.
        this._selection = Shell.Global.get().get_display().get_selection();
        this._entries = this._loadHistory();
        this._signalId = this._selection.connect('owner-changed', (_selection, type) => {
            if (type === Meta.SelectionType.SELECTION_CLIPBOARD)
                this._capture();
        });
    }

    disable() {
        if (this._signalId)
            this._selection.disconnect(this._signalId);
        this._signalId = 0;
        this._clipboard = null;
        this._selection = null;
    }

    _historyFile() {
        return Gio.File.new_for_path(GLib.build_filenamev([this._dataDir, 'history.json']));
    }

    _loadHistory() {
        try {
            const [ok, bytes] = this._historyFile().load_contents(null);
            return ok ? JSON.parse(new TextDecoder().decode(bytes)) : [];
        } catch (_) {
            return [];
        }
    }

    _privacy() {
        try {
            const path = GLib.build_filenamev([GLib.get_user_config_dir(), 'lume', 'config.json']);
            const file = Gio.File.new_for_path(path);
            const [ok, bytes] = file.load_contents(null);
            if (ok)
                return JSON.parse(new TextDecoder().decode(bytes));
        } catch (_) {}
        return {};
    }

    _allowedText(value, config) {
        if (config.clipboard_private_mode)
            return false;
        const limit = Number(config.clipboard_max_text_length || 10000);
        if (value.length > limit)
            return false;
        if (config.clipboard_filter_sensitive !== false &&
            /(?:sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._-]{20,}|password\s*[:=]\s*\S+)/i.test(value))
            return false;
        return true;
    }

    _purgeExpired(config) {
        const hours = Number(config.clipboard_auto_expire_hours || 0);
        if (hours <= 0)
            return;
        const cutoff = Date.now() - hours * 3600 * 1000;
        this._entries = this._entries.filter(entry => {
            if (!entry.captured_at)
                return true;
            return Date.parse(entry.captured_at) >= cutoff;
        });
    }

    _maxEntries(config) {
        return Math.max(1, Math.min(200, Number(config.clipboard_max_entries || MAX_ENTRIES)));
    }

    _saveHistory() {
        const output = new TextEncoder().encode(JSON.stringify(this._entries));
        this._historyFile().replace_contents(output, null, false,
            Gio.FileCreateFlags.REPLACE_DESTINATION, null);
    }

    _hash(bytes) {
        return GLib.compute_checksum_for_bytes(
            GLib.ChecksumType.SHA256,
            new GLib.Bytes(bytes),
        );
    }

    _add(entry, maxEntries = MAX_ENTRIES) {
        const last = this._entries.at(-1);
        if (last && last.content_type === entry.content_type &&
            ((entry.content_type === 'text' && last.text === entry.text) ||
             (entry.content_type === 'image' && last.image_hash === entry.image_hash)))
            return;
        this._entries.push(entry);
        this._entries = this._entries.slice(-maxEntries);
        this._saveHistory();
    }

    _capture() {
        // Read the privacy switch before touching the clipboard or history.
        // Existing history remains untouched; only future captures are blocked.
        const config = this._privacy();
        if (config.clipboard_private_mode)
            return;
        // The Qt frontend may remove or clear entries while the Shell
        // extension remains enabled.  Reload before appending so deleted
        // history held in this long-lived JS instance cannot be written back
        // the next time the user copies something.
        this._entries = this._loadHistory();
        this._purgeExpired(config);
        const type = St.ClipboardType.CLIPBOARD;
        const mimetypes = this._clipboard.get_mimetypes(type);
        if (mimetypes.includes('image/png')) {
            this._clipboard.get_content(type, 'image/png', (_clipboard, bytes) => {
                const data = bytes instanceof GLib.Bytes ? bytes.get_data() : bytes;
                if (!data?.length)
                    return;
                const maxBytes = Number(config.clipboard_max_image_bytes || 10 * 1024 * 1024);
                if (config.clipboard_private_mode || data.length > maxBytes)
                    return;
                const hash = this._hash(data);
                const path = GLib.build_filenamev([this._imagesDir, `shell_${hash}.png`]);
                Gio.File.new_for_path(path).replace_contents(data, null, false,
                    Gio.FileCreateFlags.REPLACE_DESTINATION, null);
                this._add({id: `shell_${hash}_${Date.now()}`, content_type: 'image',
                    image_path: path, image_hash: hash, captured_at: new Date().toISOString()}, this._maxEntries(config));
            });
            return;
        }
        this._clipboard.get_text(type, (_clipboard, text) => {
            const value = text?.trim();
            if (!value || !this._allowedText(value, config))
                return;
            const hash = this._hash(new TextEncoder().encode(value));
            this._add({id: `shell_${hash}_${Date.now()}`, content_type: 'text', text: value,
                captured_at: new Date().toISOString()}, this._maxEntries(config));
        });
    }
}
