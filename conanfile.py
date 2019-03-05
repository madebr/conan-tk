# -*- coding: utf-8 -*-

from conans import ConanFile, AutoToolsBuildEnvironment, tools
from conans.errors import ConanExceptionInUserConanfileMethod
from conans.util.env_reader import get_env
from conans.errors import ConanInvalidConfiguration
import os
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
    _source_subfolder = "sources_tk"
    _tcl_version = "8.6.9"
    _source_tcl_subfolder = "sources_tcl"

    def configure(self):
        if self.settings.compiler != "Visual Studio":
            del self.settings.compiler.libcxx

        if self.version.split(".")[:3] != self._tcl_version.split(".")[:3]:
            raise ConanInvalidConfiguration("Versions of tcl and tk do not match")

    def requirements(self):
        self.requires("tcl/{}@bincrafters/stable".format(self._tcl_version))

    @property
    def _is_mingw_windows(self):
        return self.settings.os == "Windows" and self.settings.compiler == "gcc"

    def config_options(self):
        if self.settings.os == "Windows" or self.options.shared:
            del self.options.fPIC

    def build_requirements(self):
        if self._is_mingw_windows:
            self.build_requires("msys2_installer/latest@bincrafters/stable")

    def source(self):
        tk_filename_version = ".".join(self.version.split(".")[:3])
        print('tk_filename_version', tk_filename_version)
        filename_tk = "tk{}-src.tar.gz".format(self.version)
        url_tk = "https://prdownloads.sourceforge.net/tcl/{}".format(filename_tk)
        sha256_tk = "8fcbcd958a8fd727e279f4cac00971eee2ce271dc741650b1fc33375fb74ebb4"

        # building tk on macos and windows requires the tcl sources
        filename_tcl = "tcl{}-src.tar.gz".format(self._tcl_version)
        url_tcl = "https://prdownloads.sourceforge.net/tcl/{}".format(filename_tcl)
        sha256_tcl = "ad0cd2de2c87b9ba8086b43957a0de3eb2eb565c7159d5f53ccbba3feb915f4e"

        def download_tcltk_source(name, filename, url, sha256, extracted_dir, source_subfolder):
            dlfilepath = os.path.join(tempfile.gettempdir(), filename)
            if os.path.exists(dlfilepath) and not get_env("TK_FORCE_DOWNLOAD", False):
                self.output.info("Skipping download. Using cached {}".format(dlfilepath))
            else:
                self.output.info("Downloading {} from {}".format(self.name, url))
                tools.download(url, dlfilepath)
            tools.check_sha256(dlfilepath, sha256)
            tools.untargz(dlfilepath)

            os.rename(extracted_dir, source_subfolder)

            for build_system in ("unix", "win", ):
                config_dir = self._get_configure_dir(build_system, source_subfolder)

                if build_system != "win":
                    # When disabling 64-bit support (in 32-bit), this test must be 0 in order to use "long long" for 64-bit ints
                    # (${tcl_type_64bit} can be either "__int64" or "long long")
                    tools.replace_in_file(os.path.join(config_dir, "configure"),
                                          "(sizeof(${tcl_type_64bit})==sizeof(long))",
                                          "(sizeof(${tcl_type_64bit})!=sizeof(long))")

                makefile_in = os.path.join(config_dir, "Makefile.in")
                # Avoid clearing CFLAGS and LDFLAGS in the makefile
                tools.replace_in_file(makefile_in, "\nCFLAGS{}".format(" " if (build_system == "win" and name == "tcl") else "\t"), "\n#CFLAGS\t")
                tools.replace_in_file(makefile_in, "\nLDFLAGS\t", "\n#LDFLAGS\t")
                tools.replace_in_file(makefile_in, "${CFLAGS}", "${CFLAGS} ${CPPFLAGS}")

        download_tcltk_source(name="tk", filename=filename_tk, url=url_tk, sha256=sha256_tk, extracted_dir="tk{}".format(tk_filename_version), source_subfolder=self._source_subfolder)
        # Building tk on windows, using the tk toolchain requires the tcl sources
        download_tcltk_source(name="tcl", filename=filename_tcl, url=url_tcl, sha256=sha256_tcl, extracted_dir="tcl{}".format(self._tcl_version), source_subfolder=self._source_tcl_subfolder)

        win_makefile_in = os.path.join(self._get_configure_dir("win", self._source_subfolder), "Makefile.in")
        tools.replace_in_file(win_makefile_in, "\nTCL_GENERIC_DIR", "\n#TCL_GENERIC_DIR")

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
                    tcldir=os.path.join(self.source_folder, self._source_tcl_subfolder),
                    target=target,
                ), cwd=self._get_configure_dir("win"),
            )

    def _build_autotools(self):
        tcl_root = self.deps_cpp_info["tcl"].rootpath
        tclConfigShPath = os.path.join(tcl_root, "lib", "tclConfig.sh")

        conf_args = [
            "--with-tcl={}".format(os.path.dirname(tclConfigShPath.replace("\\", "/"))),
            "--enable-threads",
            "--enable-shared" if self.options.shared else "--disable-shared",
            "--enable-symbols" if self.settings.build_type == "Debug" else "--disable-symbols",
            "--enable-64bit" if self.settings.arch == "x86_64" else "--disable-64bit",
            "--with-x" if self.settings.os == "Linux" else "--without-x",
            "--enable-aqua={}".format("yes" if self.settings.os == "Macos" else "no"),
        ]

        autoTools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
        if self._is_mingw_windows:
            autoTools.defines.extend(["UNICODE", "_UNICODE", "_ATL_XP_TARGETING", ])
        autoTools.configure(configure_dir=self._get_configure_dir(), args=conf_args)
        autoTools.make(args=["TCL_GENERIC_DIR={}".format(os.path.join(tcl_root, "include")).replace("\\", "/")])

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
                autoTools.make(target="install-private-headers")
            if not self._is_mingw_windows:
                shutil.rmtree(os.path.join(self.package_folder, "lib", "pkgconfig"))
        self.copy(pattern="license.terms", dst="licenses", src=self._source_subfolder)
        
        tkConfigShPath = os.path.join(self.package_folder, "lib", "tkConfig.sh")
        pkg_path = os.path.join(self.package_folder).replace('\\', '/')
        tools.replace_in_file(tkConfigShPath,
                              pkg_path,
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
        elif self.settings.os == "Windows":
            self.cpp_info.libs.extend(["netapi32", "kernel32", "user32", "advapi32", "userenv",
                                       "ws2_32", "gdi32", "comdlg32", "imm32", "comctl32",
                                       "shell32", "uuid", "ole32", "oleaut32"])
        
        tk_library = os.path.join(self.package_folder, "lib", "{}{}".format(self.name, ".".join(self.version.split(".")[:2])))
        self.output.info("Setting TCL_LIBRARY environment variable to {}".format(tk_library))
        self.env_info.TK_LIBRARY = tk_library
       
        tcl_root = self.package_folder
        self.output.info("Setting TCL_ROOT environment variable to {}".format(tcl_root))
        self.env_info.TCL_ROOT = tcl_root
