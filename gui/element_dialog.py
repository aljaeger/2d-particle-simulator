import tkinter as tk

from .fields import editable_fields, parse_values


class ElementDialog(tk.Toplevel):
    """Modal dialog with one entry per dataclass field. result is a dict, "delete", or None."""

    def __init__(self, parent, cls, values, allow_delete=False):
        super().__init__(parent)
        self.title(cls.__name__)
        self.cls = cls
        self.result = None
        self.entries = {}
        for row, f in enumerate(editable_fields(cls)):
            tk.Label(self, text=f.name).grid(row=row, column=0, sticky="e", padx=4, pady=2)
            entry = tk.Entry(self)
            entry.insert(0, values[f.name])
            entry.grid(row=row, column=1, padx=4, pady=2)
            self.entries[f.name] = entry
        row = len(self.entries)
        self.error = tk.Label(self, fg="red")
        self.error.grid(row=row, column=0, columnspan=2)
        buttons = tk.Frame(self)
        buttons.grid(row=row + 1, column=0, columnspan=2, pady=4)
        tk.Button(buttons, text="OK", command=self._ok).pack(side="left", padx=2)
        tk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=2)
        if allow_delete:
            tk.Button(buttons, text="Delete", command=self._delete).pack(side="left", padx=2)
        self.bind("<Return>", lambda _: self._ok())
        self.transient(parent)
        self.grab_set()
        parent.wait_window(self)

    def _ok(self):
        try:
            self.result = parse_values(self.cls, {k: e.get() for k, e in self.entries.items()})
        except ValueError as exc:
            self.error.config(text=str(exc))
            return
        self.destroy()

    def _delete(self):
        self.result = "delete"
        self.destroy()


def edit_values(parent, cls, values, allow_delete=False):
    return ElementDialog(parent, cls, values, allow_delete).result
