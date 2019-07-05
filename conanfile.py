# -*- coding: utf-8 -*-

from conans import ConanFile, AutoToolsBuildEnvironment, tools
from conans.errors import ConanException, ConanInvalidConfiguration, ConanExceptionInUserConanfileMethod
import os
import shutil


class TkConan(ConanFile):
    name = "tk"
    version = "8.6.9.1"
    description = "Tk is a graphical user interface toolkit that takes developing desktop applications to a higher level than conventional approaches."
    topics = ("conan", "tcl", "scripting", "programming")
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

    _source_subfolder = "source_subfolder"
    _tcl_version = "8.6.9"

    def configure(self):
        if self.settings.compiler != "Visual Studio":
            del self.settings.compiler.libcxx

        if self.version.split(".")[:3] != self._tcl_version.split(".")[:3]:
            raise ConanInvalidConfiguration("Versions of tcl and tk do not match")

        self.options["tcl"].shared = self.options.shared

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
        filename_tk = "tk{}-src.tar.gz".format(self.version)
        url_tk = "https://downloads.sourceforge.net/project/tcl/Tcl/{}/{}".format(tk_filename_version, filename_tk)
        sha256 = "8fcbcd958a8fd727e279f4cac00971eee2ce271dc741650b1fc33375fb74ebb4"

        tools.get(url_tk, sha256=sha256)

        extracted_dir = "tk{}".format(tk_filename_version)
        os.rename(extracted_dir, self._source_subfolder)

    def _fix_sources(self):
        # download_tcltk_source(name="tk", filename=filename_tk, url=url_tk, sha256=sha256, extracted_dir="tk{}".format(tk_filename_version), source_subfolder=self._source_subfolder)
        # def download_tcltk_source(name, filename, url, sha256, extracted_dir, source_subfolder):

        for build_system in ("unix", "win", ):
            config_dir = self._get_configure_dir(build_system)

            if build_system != "win":
                # When disabling 64-bit support (in 32-bit), this test must be 0 in order to use "long long" for 64-bit ints
                # (${tcl_type_64bit} can be either "__int64" or "long long")
                tools.replace_in_file(os.path.join(config_dir, "configure"),
                                      "(sizeof(${tcl_type_64bit})==sizeof(long))",
                                      "(sizeof(${tcl_type_64bit})!=sizeof(long))")

            makefile_in = os.path.join(config_dir, "Makefile.in")
            # Avoid clearing CFLAGS and LDFLAGS in the makefile
            # tools.replace_in_file(makefile_in, "\nCFLAGS{}".format(" " if (build_system == "win" and name == "tcl") else "\t"), "\n#CFLAGS\t")
            tools.replace_in_file(makefile_in, "\nLDFLAGS\t", "\n#LDFLAGS\t")
            tools.replace_in_file(makefile_in, "${CFLAGS}", "${CFLAGS} ${CPPFLAGS}")

        rules_ext_vc = os.path.join(self.source_folder, self._source_subfolder, "win", "rules-ext.vc")
        tools.replace_in_file(rules_ext_vc,
                              "\n_RULESDIR = ",
                              "\n_RULESDIR = .\n#_RULESDIR = ")
        rules_vc = os.path.join(self.source_folder, self._source_subfolder, "win", "rules.vc")
        tools.replace_in_file(rules_vc,
                              r"$(_TCLDIR)\generic",
                              r"$(_TCLDIR)\include")
        tools.replace_in_file(rules_vc,
                              "\nTCLSTUBLIB",
                              "\n#TCLSTUBLIB")
        tools.replace_in_file(rules_vc,
                              "\nTCLIMPLIB",
                              "\n#TCLIMPLIB")

        win_makefile_in = os.path.join(self._get_configure_dir("win"), "Makefile.in")
        tools.replace_in_file(win_makefile_in, "\nTCL_GENERIC_DIR", "\n#TCL_GENERIC_DIR")

        tools.replace_in_file(os.path.join(self.source_folder, self._source_subfolder, "win", "rules.vc"),
                              "\ncwarn = $(cwarn) -WX",
                              "\n# cwarn = $(cwarn) -WX")

    def system_requirements(self):
        if tools.os_info.with_apt:
            packages = []
            installer = tools.SystemPackageTool()
            if self.settings.arch == "x86":
                arch_suffix = ":i386"
            elif self.settings.arch == "x86_64":
                arch_suffix = ":amd64"
            else:
                raise ConanException("Unsupported arch: {}".format(str(self.settings.arch)))
            packages.extend(["libx11-dev%s" % arch_suffix,
                             "libxext-dev%s" % arch_suffix,
                             "libxss-dev%s" % arch_suffix,
                             "libxft-dev%s" % arch_suffix,
                             "libfontconfig1-dev%s" % arch_suffix])
            for package in packages:
                installer.install(package)
        if tools.os_info.with_yum:
            packages = []
            installer = tools.SystemPackageTool()
            if self.settings.arch == "x86":
                arch_suffix = ".i686"
            elif self.settings.arch == "x86_64":
                arch_suffix = ".x86_64"
            else:
                raise ConanException("Unsupported arch: {}".format(str(self.settings.arch)))
            packages.extend(["libX11-devel%s" % arch_suffix,
                             "libXext-devel%s" % arch_suffix,
                             "libXScrnSaver-devel%s" % arch_suffix,
                             "libXft-devel%s" % arch_suffix,
                             "fontconfig-devel"])
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

    def _get_configure_dir(self, build_system=None):
        if build_system is None:
            build_system = self._get_default_build_system()
        if build_system not in ["win", "unix", "macosx"]:
            raise ConanExceptionInUserConanfileMethod("Invalid build system: {}".format(build_system))
        return os.path.join(self.source_folder, self._source_subfolder, build_system)

    def _build_nmake(self, target="release"):
        # https://core.tcl.tk/tips/doc/trunk/tip/477.md
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
        # https://core.tcl.tk/tk/tktview?name=3d34589aa0
        # https://wiki.tcl-lang.org/page/Building+with+Visual+Studio+2017
        tcl_lib_path = os.path.join(self.deps_cpp_info["tcl"].rootpath, "lib")
        tclimplib, tclstublib = None, None
        for lib in os.listdir(tcl_lib_path):
            if not lib.endswith(".lib"):
                continue
            if lib.startswith("tcl{}".format("".join(self.version.split(".")[:2]))):
                tclimplib = os.path.join(tcl_lib_path, lib)
            elif lib.startswith("tclstub{}".format("".join(self.version.split(".")[:2]))):
                tclstublib = os.path.join(tcl_lib_path, lib)

        if tclimplib is None or tclstublib is None:
            raise ConanException("tcl dependency misses tcl and/or tclstub library")
        winsdk_version = None
        if self.settings.compiler.version == 15:
            winsdk_version = "10.0.15063.0"
        with tools.vcvars(self.settings, winsdk_version=winsdk_version):
            tcldir = self.deps_cpp_info["tcl"].rootpath.replace("/", "\\\\")
            self.run(
                """nmake -nologo -f "{cfgdir}/makefile.vc" INSTALLDIR="{pkgdir}" OPTS={opts} TCLDIR="{tcldir}" TCL_LIBRARY="{tcl_library}" TCLIMPLIB="{tclimplib}" TCLSTUBLIB="{tclstublib}" {target}""".format(
                    cfgdir=self._get_configure_dir("win"),
                    pkgdir=self.package_folder,
                    opts=",".join(opts),
                    tcldir=tcldir,
                    tclstublib=tclstublib,
                    tclimplib=tclimplib,
                    tcl_library=self.deps_env_info['tcl'].TCL_LIBRARY.replace("\\", "/"),
                    target=target,
                ), cwd=self._get_configure_dir("win"),
            )

    @property
    def _host_triplet(self):
        return False
        # return tools.get_gnu_triplet(str(self.settings.os), str(self.settings.arch), str(self.settings.compiler))

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
        autoTools.configure(configure_dir=self._get_configure_dir(), args=conf_args, host=self._host_triplet)
        autoTools.make(args=["TCL_GENERIC_DIR={}".format(os.path.join(tcl_root, "include")).replace("\\", "/")])

    def build(self):
        self._fix_sources()
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
        if os.path.exists(tkConfigShPath):
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
        if self.settings.os == "Linux":
            libs.extend(["X11", "Xss", "Xext", "Xft", "fontconfig"])
        self.cpp_info.libs = libs
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
        self.output.info("Setting TK_LIBRARY environment variable to {}".format(tk_library))
        self.env_info.TK_LIBRARY = tk_library
       
        tcl_root = self.package_folder
        self.output.info("Setting TCL_ROOT environment variable to {}".format(tcl_root))
        self.env_info.TCL_ROOT = tcl_root
