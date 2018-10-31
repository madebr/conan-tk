# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import time

from conans import tools, ConanFile, CMake


class TclTestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    @property
    def need_xvfb(self):
        return tools.get_env("DISPLAY", None) is None

    def install_xvfb(self):
        if not shutil.which("Xvfb"):
            if tools.os_info.with_apt:
                installer = tools.SystemPackageTool()
                installer.install("xvfb")
            if tools.os_info.with_yum:
                installer = tools.SystemPackageTool()
                installer.install("xorg-x11-server-Xvfb")

    def system_requirements(self):
        if self.need_xvfb:
            self.install_xvfb()

    def imports(self):
        self.copy("*.dll", dst="bin", src="bin")
        self.copy("*.dylib*", dst="bin", src="lib")
        self.copy("*.so*", dst="bin", src="lib")

    def test(self):
        process = None
        extra_env = {}
        if self.need_xvfb:
            self.install_xvfb()
            display = ":8"
            process = subprocess.Popen(["Xvfb", display])
            extra_env = {"DISPLAY": display}
            time.sleep(1)
        with tools.environment_append(extra_env):
            bin_path = os.path.join("bin", "test_package")
            self.run(bin_path, run_environment=True)
        if process:
            process.kill()
