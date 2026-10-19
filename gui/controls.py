import tkinter as tk

from .fields import ELEMENT_TYPES

SETTINGS = (("T", 10.0, float), ("n_steps", 1000, int), ("steps_per_frame", 5, int), ("N", 10, int))


class Controls:
    def __init__(self, root, app):
        root.title("Controls")
        frame = tk.Frame(root, padx=8, pady=8)
        frame.pack()
        for cls in ELEMENT_TYPES:
            tk.Button(frame, text=f"Add {cls.__name__}", width=20,
                      command=lambda c=cls: app.add_element(c)).pack(fill="x")
        tk.Button(frame, text="Edit Source", width=20, command=app.edit_source).pack(fill="x", pady=(8, 0))
        tk.Button(frame, text="Save configuration", width=20, command=app.save_config).pack(fill="x")

        self.vars, self.entries, self.types = {}, {}, {}
        self.valid = {name: default for name, default, _ in SETTINGS}
        for name, default, typ in SETTINGS:
            row = tk.Frame(frame)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=name, width=14, anchor="w").pack(side="left")
            self.vars[name] = tk.StringVar(value=str(default))
            self.entries[name] = tk.Entry(row, textvariable=self.vars[name], width=8)
            self.entries[name].pack(side="left")
            self.types[name] = typ

        self.loop = tk.BooleanVar(value=False)
        tk.Checkbutton(frame, text="Loop (resample when all particles are dead)", variable=self.loop,
                       anchor="w").pack(fill="x", pady=(8, 0))
        self.cumulative = tk.BooleanVar(value=False)
        tk.Checkbutton(frame, text="Cumulative detector counts (since Reset)", variable=self.cumulative,
                       anchor="w", command=app.refresh).pack(fill="x")
        self.hide_particles = tk.BooleanVar(value=False)
        tk.Checkbutton(frame, text="Hide particles and tracks", variable=self.hide_particles,
                       anchor="w", command=app.refresh).pack(fill="x")
        self.play_button = tk.Button(frame, text="Play", width=20, command=app.toggle_play)
        self.play_button.pack(fill="x")
        tk.Button(frame, text="Step", width=20, command=app.step).pack(fill="x")
        tk.Button(frame, text="Reset", width=20, command=app.reset).pack(fill="x")
        tk.Button(frame, text="Resample particles", width=20, command=app.resample).pack(fill="x")
        self.status = tk.Label(frame, text="", anchor="w", width=28)
        self.status.pack(fill="x", pady=(8, 0))

    def set_playing(self, playing):
        self.play_button.config(text="Pause" if playing else "Play")

    def set_status(self, text):
        self.status.config(text=text)

    def _get(self, name):
        """Parsed positive value of an entry; invalid text keeps the last valid value and turns the box red."""
        try:
            value = self.types[name](self.vars[name].get())
            if value <= 0:
                raise ValueError
        except ValueError:
            self.entries[name].config(bg="misty rose")
            return self.valid[name]
        self.entries[name].config(bg="white")
        self.valid[name] = value
        return value

    def loop_enabled(self):
        return self.loop.get()

    def cumulative_enabled(self):
        return self.cumulative.get()

    def particles_visible(self):
        return not self.hide_particles.get()

    def settings(self):
        return {name: self._get(name) for name, _, _ in SETTINGS} | {
            "loop": self.loop.get(), "cumulative": self.cumulative.get(),
            "hide_particles": self.hide_particles.get()}

    def apply_settings(self, settings):
        for name, _, _ in SETTINGS:
            if name in settings:
                self.vars[name].set(str(settings[name]))
        self.loop.set(bool(settings.get("loop", False)))
        self.cumulative.set(bool(settings.get("cumulative", False)))
        self.hide_particles.set(bool(settings.get("hide_particles", False)))

    def n_particles(self):
        return self._get("N")

    def values(self):
        return self._get("T"), self._get("n_steps"), self._get("steps_per_frame")
