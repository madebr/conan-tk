# -*- coding: utf-8 -*-

from conans import ConanFile, AutoToolsBuildEnvironment, tools
from conans.errors import ConanException, ConanExceptionInUserConanfileMethod
from conans.util.env_reader import get_env
from conans.errors import ConanInvalidConfiguration
import os
import re
import shutil
import tempfile


class TkConan(ConanFile):
    name = "tk"
    version = "8.6.9"
    description = "Tk is a graphical user interface toolkit that takes developing desktop applications to a higher level than conventional approaches."
    topics = ["conan", "tcl", "scripting", "programming"]
    url = "https://github.com/bincrafters/conan-tk"
    homepage = "https://tcl.tk"
    author = "Bincrafters <bincrafters@gmail.com>"
    license = "TCL"
    exports = ["LICENSE.md"]
    settings = "os", "compiler", "build_type", "arch"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
    }
    _source_subfolder = "sources_tk"
    _source_tcl_subfolder = "sources_tcl"

    def requirements(self):
        self.requires("tcl/{}@bincrafters/stable".format(self.version))

    @property
    def _is_mingw_windows(self):
        return self.settings.os == "Windows" and self.settings.compiler == "gcc"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
        else:
            if self.options.shared:
                del self.options.fPIC  # Does not make sense.

    def configure(self):
        if self.settings.compiler != "Visual Studio":
            del self.settings.compiler.libcxx

    def build_requirements(self):
        if self._is_mingw_windows:
            self.build_requires("msys2_installer/latest@bincrafters/stable")

    def source(self):
        filename_tk = "tk{}-src.tar.gz".format(self.version)
        url_tk = "https://prdownloads.sourceforge.net/tcl/{}".format(filename_tk)
        sha256_tk = "d3f9161e8ba0f107fe8d4df1f6d3a14c30cc3512dfc12a795daa367a27660dac"

        # building tk on windows requires the tcl source
        filename_tcl = "tcl{}-src.tar.gz".format(self.version)
        url_tcl = "https://prdownloads.sourceforge.net/tcl/{}".format(filename_tcl)
        sha256_tcl = "ad0cd2de2c87b9ba8086b43957a0de3eb2eb565c7159d5f53ccbba3feb915f4e"

        for name, filename, url, sha256, source_subfolder in (("tk", filename_tk, url_tk, sha256_tk, self._source_subfolder),
                                            ("tcl", filename_tcl, url_tcl, sha256_tcl, self._source_tcl_subfolder)):
            dlfilepath = os.path.join(tempfile.gettempdir(), filename)
            if os.path.exists(dlfilepath) and not get_env("TK_FORCE_DOWNLOAD", False):
                self.output.info("Skipping download. Using cached {}".format(dlfilepath))
            else:
                self.output.info("Downloading {} from {}".format(self.name, url))
                tools.download(url, dlfilepath)
            tools.check_sha256(dlfilepath, sha256)
            tools.untargz(dlfilepath)

            extracted_dir = "{}{}".format(name, self.version)
            os.rename(extracted_dir, source_subfolder)

            unix_config_dir = self._get_configure_dir("unix", source_subfolder)
            # When disabling 64-bit support (in 32-bit), this test must be 0 in order to use "long long" for 64-bit ints
            # (${tcl_type_64bit} can be either "__int64" or "long long")
            tools.replace_in_file(os.path.join(unix_config_dir, "configure"),
                                  "(sizeof(${tcl_type_64bit})==sizeof(long))",
                                  "(sizeof(${tcl_type_64bit})!=sizeof(long))")

            unix_makefile_in = os.path.join(unix_config_dir, "Makefile.in")
            # Avoid clearing CFLAGS and LDFLAGS in the makefile
            tools.replace_in_file(unix_makefile_in, "\nCFLAGS\t", "\n#CFLAGS\t")
            tools.replace_in_file(unix_makefile_in, "\nLDFLAGS\t", "\n#LDFLAGS\t")
            tools.replace_in_file(unix_makefile_in, "${CFLAGS}", "${CFLAGS} ${CPPFLAGS}")

    def config_options(self):
        if self.settings.compiler == "Visual Studio" or self.options.shared:
            del self.options.fPIC

    def system_requirements(self):
        if tools.os_info.with_apt:
            packages = []
            installer = tools.SystemPackageTool()
            if self.settings.arch == "x86":
                arch_suffix = ":i386"
            elif self.settings.arch == "x86_64":
                arch_suffix = ":amd64"
            packages.extend(["libx11-dev%s" % arch_suffix,
                             "libxext-dev%s" % arch_suffix,
                             "libxss-dev%s" % arch_suffix])
            for package in packages:
                installer.install(package)
        if tools.os_info.with_yum:
            packages = []
            installer = tools.SystemPackageTool()
            if self.settings.arch == "x86":
                arch_suffix = ".i686"
            elif self.settings.arch == "x86_64":
                arch_suffix = ".x86_64"
            packages.extend(["libX11-devel%s" % arch_suffix,
                             "libXext-devel%s" % arch_suffix,
                             "libXScrnSaver-devel%s" % arch_suffix])
            for package in packages:
                installer.install(package)

    def _get_default_build_system(self):
        if self.settings.os == "Macos":
            return "macosx"
        elif self.settings.os == "Linux":
            return "unix"
        elif self.settings.os == "Windows":
            return "win"
        else:
            raise ConanExceptionInUserConanfileMethod("Unknown settings.os={}".format(self.settings.os))

    def _get_configure_dir(self, build_system=None, source_subfolder=None):
        if source_subfolder is None:
            source_subfolder = self._source_subfolder
        if build_system is None:
            build_system = self._get_default_build_system()
        if build_system not in ["win", "unix", "macosx"]:
            raise ConanExceptionInUserConanfileMethod("Invalid build system: {}".format(build_system))
        return os.path.join(self.source_folder, source_subfolder, build_system)

    def _get_auto_tools(self):
        autoTools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
        return autoTools

    def _build_nmake(self, target="release"):
        # Fails for VS2017+: https://core.tcl.tk/tips/doc/trunk/tip/477.md
        opts = []
        if not self.options.shared:
            opts.append("static")
        if self.settings.build_type == "Debug":
            opts.append("symbols")
        if "MD" in self.settings.compiler.runtime:
            opts.append("msvcrt")
        else:
            opts.append("nomsvcrt")
        if "d" in self.settings.compiler.runtime:
            opts.append("unchecked")
        vcvars_command = tools.vcvars_command(self.settings)
        self.run(
            """{vcvars} && nmake -nologo -f "{cfgdir}/makefile.vc" shell INSTALLDIR="{pkgdir}" OPTS={opts} TCLDIR="{tcldir}" {target}""".format(
                vcvars=vcvars_command,
                cfgdir=self._get_configure_dir("win"),
                pkgdir=self.package_folder,
                opts=",".join(opts),
                tcldir=os.path.join(self.source_folder, self._source_tcl_subfolder),  # self.deps_cpp_info["tcl"].rootpath,
                target=target,
            ), cwd=self._get_configure_dir("win"),
        )

    def _patch_tclConfig_sh(self):
        try:
            tclConfig_sh = open(os.path.join(self.deps_cpp_info["tcl"].rootpath, "lib", "tclConfig.sh"), "r").read()
            match = re.search("^TCL_PREFIX='(.*)'$", tclConfig_sh, flags=re.MULTILINE)
            tclOriginalPrefix = match.group(1)

            tclCurrentPrefix = self.deps_cpp_info["tcl"].rootpath
            newTclConfig_sh = tclConfig_sh.replace(tclOriginalPrefix, tclCurrentPrefix)

            newTclConfig_sh_path = os.path.join(self.build_folder, "tclConfig.sh")
            open(newTclConfig_sh_path, "w").write(newTclConfig_sh)
        except (AttributeError, FileNotFoundError):
            raise ConanInvalidConfiguration("Patching tclConfig.sh failed")
        return newTclConfig_sh_path

    def _build_autotools(self):
        tclConfigShPath = self._patch_tclConfig_sh()
        conf_args = [
            "--with-tcl={}".format(os.path.dirname(tclConfigShPath.replace("\\", "/"))),
            "--enable-threads",
            "--enable-shared" if self.options.shared else "--disable-shared",
            "--enable-symbols" if self.settings.build_type == "Debug" else "--disable-symbols",
            "--enable-64bit" if self.settings.arch == "x86_64" else "--disable-64bit",
        ]
        if self.settings.os == "Linux":
            conf_args.append("--with-x")
        elif self.settings.os == "Macos":
            conf_args.append("--enable-aqua")
        autoTools = self._get_auto_tools()
        autoTools.configure(configure_dir=self._get_configure_dir(), args=conf_args)

        try:
            with tools.chdir(self.build_folder):
                autoTools.make()
        except ConanException:
            self.output.error("make failed!")
            self.output.info("Outputting config.log")
            self.output.info(open(os.path.join(self.build_folder, "config.log")).read())
            raise

    def build(self):
        if self.settings.compiler == "Visual Studio":
            self._build_nmake()
        else:
            self._build_autotools()

    def package(self):
        if self.settings.compiler == "Visual Studio":
            self._build_nmake("install")
        else:
            with tools.chdir(self.build_folder):
                autoTools = self._get_auto_tools()
                autoTools.install()
            shutil.rmtree(os.path.join(self.package_folder, "lib", "pkgconfig"))
        self.copy(pattern="license.terms", dst="licenses", src=self._source_subfolder)

    def package_info(self):
        libs = tools.collect_libs(self)
        libdirs = ["lib"]
        if self.settings.os == "Linux":
            libs.extend(["X11", "Xss", "Xext"])
        defines = []
        self.cpp_info.defines = defines
        self.cpp_info.bindirs = ["bin"]
        self.cpp_info.libdirs = libdirs
        self.cpp_info.libs = libs
        self.cpp_info.includedirs = ["include"]
        self.env_info.TK_LIBRARY = os.path.join(self.package_folder, "lib", "{}{}".format(self.name, ".".join(self.version.split(".")[:2])))
        if self.settings.os == "Macos":
            self.cpp_info.exelinkflags.append("-framework Cocoa")
            self.cpp_info.sharedlinkflags = self.cpp_info.exelinkflags
