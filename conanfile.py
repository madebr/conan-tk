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
    version = "8.6.9.1"
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
    _source_subfolder = "sources"
    _tcl_version = "8.6.9"

    def configure(self):
        if self.version.split(".")[:3] != self._tcl_version.split(".")[:3]:
            raise ConanInvalidConfiguration("Versions of tcl and tk do not match")

    def requirements(self):
        self.requires("tcl/{}@bincrafters/stable".format(self._tcl_version))

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
        tk_filename_version = ".".join(self.version.split(".")[:3])
        print('tk_filename_version', tk_filename_version)
        filename_tk = "tk{}-src.tar.gz".format(self.version)
        url_tk = "https://prdownloads.sourceforge.net/tcl/tk{}-src.tar.gz".format(filename_tk)
        sha256_tk = "8fcbcd958a8fd727e279f4cac00971eee2ce271dc741650b1fc33375fb74ebb4"

        name, filename, url, sha256, extracted_dir, source_subfolder = "tk", filename_tk, url_tk, sha256_tk, "tk{}".format(tk_filename_version), self._source_subfolder

        dlfilepath = os.path.join(tempfile.gettempdir(), filename)
        if os.path.exists(dlfilepath) and not get_env("TK_FORCE_DOWNLOAD", False):
            self.output.info("Skipping download. Using cached {}".format(dlfilepath))
        else:
            self.output.info("Downloading {} from {}".format(self.name, url))
            tools.download(url, dlfilepath)
        tools.check_sha256(dlfilepath, sha256)
        tools.untargz(dlfilepath)

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

    def _build_nmake(self, target="release"):
        # Fails for VS2017+:
        # https://core.tcl.tk/tips/doc/trunk/tip/477.md
        # https://core.tcl.tk/tk/tktview?name=3d34589aa0
        opts = []
        if not self.options.shared:
            opts.append("static")
        if self.settings.build_type == "Debug":
            opts.append("symbols")
        if "MD" in self.settings.compiler.runtime:
            opts.append("msvcrt")
        else:
            opts.append("nomsvcrt")
        if "d" not in self.settings.compiler.runtime:
            opts.append("unchecked")
        with tools.vcvars(self.settings):
            self.run(
                """nmake -nologo -f "{cfgdir}/makefile.vc" shell INSTALLDIR="{pkgdir}" OPTS={opts} TCLDIR="{tcldir}" {target}""".format(
                    cfgdir=self._get_configure_dir("win"),
                    pkgdir=self.package_folder,
                    opts=",".join(opts),
                    #tcldir=os.path.join(self.source_folder, self._source_tcl_subfolder),  # self.deps_cpp_info["tcl"].rootpath,
                    target=target,
                ), cwd=self._get_configure_dir("win"),
            )

    def _build_autotools(self):
        # FIXME: move this fixing of tclConfig.sh to tcl
        tcl_root = self.deps_cpp_info["tcl"].rootpath
        tclConfigShPath = os.path.join(tcl_root, "lib", "tclConfig.sh")
        tools.replace_in_file(tclConfigShPath,
                              os.path.join(self.package_folder),
                              tcl_root,
                              strict=False)
        tools.replace_in_file(tclConfigShPath,
                              "TCL_BUILD_",
                              "#TCL_BUILD_",
                              strict=False)

        conf_args = [
            "--with-tcl={}".format(os.path.dirname(tclConfigShPath.replace("\\", "/"))),
            "--enable-threads",
            "--enable-shared" if self.options.shared else "--disable-shared",
            "--enable-symbols" if self.settings.build_type == "Debug" else "--disable-symbols",
            "--enable-64bit" if self.settings.arch == "x86_64" else "--disable-64bit",
            "--with-x" if self.settings.os == "Linux" else "--without-x",
            "--enable-aqua={}".format("yes" if self.settings.os == "Macos" else "no"),  # autotools fails using aqua
        ]

        autoTools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
        #autoTools.include_paths.append(os.path.join(self.source_folder, self._source_tcl_subfolder, "generic"))
        #autoTools.include_paths.append(os.path.join(self.source_folder, self._source_tcl_subfolder, "unix"))
        autoTools.link_flags.extend(["-framework", "Cocoa"])
        os.environ['PATH'] = self.deps_cpp_info['tcl'].rootpath + os.path.pathsep + os.environ['PATH']
        autoTools.configure(configure_dir=self._get_configure_dir(), args=conf_args)

        try:
            with tools.chdir(self.build_folder):
                autoTools.make()
        except ConanException:
            #self.output.error("make failed!")
            #self.output.info("Outputting config.log")
            #self.output.info(open(os.path.join(self.build_folder, "config.log")).read())
            #self.output.info("Outputting config.status")
            #self.output.info(open(os.path.join(self.build_folder, "config.status")).read())
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
                autoTools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
                autoTools.install()
            shutil.rmtree(os.path.join(self.package_folder, "lib", "pkgconfig"))
        self.copy(pattern="license.terms", dst="licenses", src=self._source_subfolder)
        
        tkConfigShPath = os.path.join(self.package_folder, "lib", "tkConfig.sh")
        tools.replace_in_file(tkConfigShPath,
                              os.path.join(self.package_folder),
                              "${TK_ROOT}")
        tools.replace_in_file(tkConfigShPath,
                              "\nTK_BUILD_",
                              "\n#TK_BUILD_")
        tools.replace_in_file(tkConfigShPath,
                              "\nTK_SRC_DIR",
                              "\n#TK_SRC_DIR")

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
        if self.settings.os == "Macos":
            self.cpp_info.exelinkflags.append("-framework CoreFoundation")
            self.cpp_info.exelinkflags.append("-framework Cocoa")
            self.cpp_info.exelinkflags.append("-framework Carbon")
            self.cpp_info.exelinkflags.append("-framework IOKit")
            self.cpp_info.sharedlinkflags = self.cpp_info.exelinkflags
        
        tk_library = os.path.join(self.package_folder, "lib", "{}{}".format(self.name, ".".join(self.version.split(".")[:2])))
        self.output.info("Setting TCL_LIBRARY environment variable to {}".format(tk_library))
        self.env_info.TK_LIBRARY = tk_library
       
        tcl_root = self.package_folder
        self.output.info("Setting TCL_ROOT environment variable to {}".format(tcl_root))
        self.env_info.TCL_ROOT = tcl_root
