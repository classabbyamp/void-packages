#!/usr/bin/python3

from enum import IntEnum
from fnmatch import fnmatch
from os import environ
from sys import stderr

from dewey import Version

VERBOSE = len(environ.get("XBPS_UPDATE_CHECK_VERBOSE", "")) > 0
NOCOLORS = len(environ.get("NOCOLORS", "")) > 0

class LogLevel(IntEnum):
	Info = 0
	Warn = 1
	Err = 2

def log(*msg, level: LogLevel = LogLevel.Info):
	pfx = "=>"
	sfx = "\n"
	if not NOCOLORS:
		lvl = "\033[{}m"
		match level:
			case LogLevel.Warn:
				lvl = lvl.format(33)
			case LogLevel.Err:
				lvl = lvl.format(31)
			case _:
				lvl = ""
		pfx = f"\033[1m{lvl}=>"
		sfx = "\033[m\n"
	if VERBOSE or level > LogLevel.Info:
		print(pfx, *msg, end=sfx, file=stderr)


try:
	# use python3-regex to achieve greater compatibility with existing PCREs
	import regex
	import requests
except ImportError as e:
	log(f"{e}. Is python3-{e.name} installed?", level=LogLevel.Err)
	raise SystemExit(1)

try:
	import github3

	# gh = github3.login()
except ImportError as e:
	log(f"{e}. Is python3-{e.name} installed?", level=LogLevel.Warn)
	log("Disabling GitHub API support", level=LogLevel.Warn)
	gh = None

REQUEST_OPTS = {
	"timeout": (3.05, 10),
	"verify": False,
}
HEADERS = {
	"User-Agent": f"xbps-src-update-check/{environ.get('XBPS_SRC_VERSION')}",
}
HEADERS_ACCEPT = HEADERS.copy()
HEADERS_ACCEPT["Accept"] = ",".join([
	"text/html",
	"application/xhtml+xml",
	"application/xml",
	"text/plain",
	"application/rss+xml",
	"application/json"
])


def esc(s: str) -> str:
	return regex.escape(s, special_only=True, literal_spaces=True)

# def clean_pcre(pat: str, vars: dict[str, str]) -> str:
def clean_pcre(pat: str) -> str:
	# replace \Q...\E with esc(...)
	for m in regex.finditer(r"\\Q(.*)\\E", pat):
		# TODO?: if it contains a variable definition, try to evaluate it
		# note that the bash update-check *doesn't* do this, e.g. in the case of single-quoted strings
		# example: pattern='/archive/refs/tags/(v?|\Q${pkgname}\E-)?\K[\d\._]+(?=\.tar\.gz")'
		# partial implementation (doesn't work perfectly if multiple variables exist in the string):
		#
		# val = regex.sub(r"\$\{?([a-zA-Z0-9_]+)\}?", r"{\1}", m.group(1))
		# try:
		# 	val = val.format(**vars)
		# except KeyError as e:
		# 	var = str(e).strip("'")
		# 	if (repl := environ.get(var, None)) is not None:
		# 		val = val.format(**{var: repl})
		# 	else:
		# 		raise ValueError(f"unable to get value of {e} when parsing pattern")
		val = m.group(1)
		pat = pat.replace(m.group(0), esc(val))
	return pat

def check_ignore(ver, ignore):
	for ig in ignore:
		if fnmatch(str(ver), ig):
			if VERBOSE:
				print(f"ignored {ver} due to {ig}")
			return False
	return True


if __name__ == "__main__":
	pkgname = environ.get("pkgname", "")
	sourcepkg = environ.get("sourcepkg", "")
	homepage = environ.get("homepage", "")
	distfiles = environ.get("distfiles", "")

	site = environ.get("site", "")
	pattern = environ.get("pattern", "")
	ignore = environ.get("ignore", "").split()
	version = environ.get("version", "")
	single_dir = len(environ.get("single_directory", "")) > 0
	vdprefix = environ.get("vdprefix", "")
	vdsuffix = environ.get("vdsuffix", "")

	urls = []

	if site:
		urls += [site]
	else:
		# only consider versions that exist in ftp.gnome.org
		if "ftp.gnome.org" not in distfiles:
			urls += [homepage]
		urls += [d.rpartition('/')[0] + "/" for d in distfiles.split()]  # "${i%/*}/"

	newurls = []
	url: str
	for url in urls:
		rx = None
		newurls.append(url)
		if single_dir:
			continue

		pat = ""
		urlpfx = url
		urlsfx = ""
		dirpfx = ""

		no_dir_domains = [
			".voidlinux.", "sourceforge.net/sourceforge", "code.google.com", "googlecode", "launchpad.net",
			"cpan.", "pythonhosted.org", "github.com", "//gitlab.", "bitbucket.org", "ftp.gnome.org",
			"kernel.org/pub/linux/kernel/", "cran.r-project.org/src/contrib", "rubygems.org", "crates.io",
			"codeberg.org", "hg.sr.ht", "git.sr.ht"
		]
		if not any(x in url for x in no_dir_domains):
			vdpfx = vdprefix if vdprefix else rf"|v|{esc(pkgname)}"
			vdsfx = vdsuffix if vdsuffix else r"|\.x"
			rex = regex.compile(rf"""[^/]+//[^/]+(/.+)?/(?:{vdpfx})(?=[-_.0-9]*[0-9](?<!{esc(pkgname)})(?:{vdsfx})/)""")
			if match := rex.match(url):
				urlpfx, _, dirpfx = match.group(0).rpartition("/")  # "${match%/*}", "${match##*/}"
				urlpfx += "/"
				urlsfx = url.removeprefix(urlpfx).partition("/")[2]  # "${urlsfx#$urlpfx}", "${urlsfx#*/}"
				rx = regex.compile(
					rf"""href=["']?(?:{esc(urlpfx)})?\.?/?\K{esc(dirpfx)}[-_.0-9]*[0-9](?:{vdsfx})["'/]""",
					flags=regex.IGNORECASE
				)

		if rx:
			log(f"(folder) fetching {urlpfx} and scanning with {rx.pattern}")
			try:
				with requests.get(urlpfx, **REQUEST_OPTS, headers=HEADERS) as resp:
					if not resp.ok:
						log(f"Request failed: {resp.status_code} ({resp.reason})")
					matches = sorted((Version(x.group(0)) for x in rx.finditer(resp.text)), reverse=True)
					for newver in matches:
						if url == (newurl := urlpfx + str(newver) + urlsfx):
							break
						newurls.append(newurl)
			except requests.RequestException as e:
				log(f"Request failed: {e.__class__.__name__}")

	newurls = sorted(list(set(newurls)))
	fetched = []
	versions = set()
	for url in newurls:
		rx = None
		if not site:
			if "sourceforge.net/sourceforge" in url:
				pkgurlname = url.split("/")[4]
				url = f"https://sourceforge.net/projects/{pkgurlname}/rss?limit=200"
			elif "code.google.com" in url or "googlecode" in url:
				url = f"http://code.google.com/p/{pkgname}/downloads/list"
			elif "launchpad.net" in url:
				pkgurlname = url.split("/")[4]
				url = f"https://launchpad.net/{pkgurlname}/+download"
			elif "cpan." in url:
				pkgname = pkgname.removeprefix("perl-")
			elif "pythonhosted.org" in url:
				pkgname = pkgname.removeprefix("python-")
				pkgname = pkgname.removeprefix("python3-")
				url = f"https://pypi.org/simple/{pkgname}"
			elif "github.com" in url:
				pkgurlname = "/".join(url.split("/")[3:5])
				url = f"https://github.com/{pkgurlname}/tags"
				rx = rf"""/archive/refs/tags/(?:v?|{esc(pkgname)}-)?\K[\d.]+(?=\.tar\.gz")"""
			elif "//gitlab." in url:
				if "/-/" in url:
					pkgurlname = url.rpartition("/-/")[0]
				else:
					pkgurlname = "/".join(url.split("/")[:5])
				url = pkgurlname + "/tags"
				rx = rf"""/archive/[^/]+/{esc(pkgname)}-v?\K[\d.]+(?=\.tar\.gz")"""
			elif "bitbucket.org" in url:
				pkgurlname = "/".join(url.split("/")[3:5])
				url = f"https://bitbucket.org/{pkgurlname}/downloads"
				rx = rf"""/(get|downloads)/(?:v?|{esc(pkgname)}-)?\K[\d.]+(?=\.tar)"""
			elif "ftp.gnome.org" in url or "download.gnome.org" in url:
				url = f"https://download.gnome.org/sources/{pkgname}/cache.json"
				if not pattern:
					pattern = rf"""{esc(pkgname)}-\K(?:0|[13]\.[0-9]*[02468]|[4-9][0-9]+)\.[0-9.]*[0-9](?=\.tar)"""
			elif "kernel.org/pub/linux/kernel/" in url:
				rx = rf"""linux-\K{esc(version.rpartition('.')[0])}[\d.]+(?=\.tar\.xz)"""
			elif "cran.r-project.org/src/contrib" in url:
				pkgurlname = pkgname.removeprefix('R-cran-')
				rx = rf"""\b{esc(pkgurlname)}_\K\d+(?:\.\d+)*(?:-\d+)?(?=\.tar)"""
			elif "rubygems.org" in url:
				pkgurlname = pkgname.removeprefix("ruby-")
				url = f"https://rubygems.org/gems/{pkgurlname}"
				rx = rf"""href="/gems/{esc(pkgurlname)}/versions/\K[\d.]*(?=")"""
			elif "crates.io" in url:
				pkgurlname = pkgname.removeprefix("rust-")
				url = f"https://crates.io/api/v1/crates/{pkgurlname}"
				rx = rf"""/crates/{esc(pkgurlname)}/\K[0-9.]*(?=/download)"""
			elif "codeberg.org" in url:
				pkgurlname = "/".join(url.split("/")[3:5])
				url = f"https://codeberg.org/{pkgurlname}/tags"
				rx = rf"""/archive/(?:v-?|{esc(pkgname)}-)?\K[\d.]+(?=\.tar\.gz)"""
			elif "hg.sr.ht" in url:
				pkgurlname = "/".join(url.split("/")[3:5])
				url = f"https://hg.sr.ht/{pkgurlname}/tags"
				rx = rf"""/archive/(?:v?|{esc(pkgname)}-)?\K[\d.]+(?=\.tar\.gz")"""
			elif "git.sr.ht" in url:
				pkgurlname = "/".join(url.split("/")[3:5])
				url = f"https://git.sr.ht/{pkgurlname}/refs"
				rx = rf"""/archive/(?:v?|{esc(pkgname)}-)?\K[\d.]+(?=\.tar\.gz")"""
			elif "pkgs.fedoraproject.org" in url:
				url = f"https://pkgs.fedoraproject.org/repo/pkgs/{pkgname}"

		if pattern:
			# see comment in clean_pcre()
			# vars = {
			# 	"pkgname": pkgname,
			# 	"sourcepkg": sourcepkg,
			# 	"homepage": homepage,
			# 	"distfiles": distfiles,
			# 	"site": site,
			# 	"ignore": ignore,
			# 	"version": version,
			# 	"single_dir": single_dir,
			# 	"vdprefix": vdprefix,
			# 	"vdsuffix": vdsuffix,
			# }
			# try:
			# 	rx = clean_pcre(pattern, vars)
			# except ValueError as e:
			# 	log(e)
			# 	continue
			rx = clean_pcre(pattern)
		elif not rx:
			rx = (
				rf"""(?<!-)\b{esc(pkgname)}[-_]?(?:(?:src|source)[-_])?v?\K([^-/_\s]*?\d[^-/_\s]*?)"""
				r"""(?=(?:[-_.](?:src|source|orig))?\.(?:[jt]ar|shar|t[bglx]z|tbz2|zip))\b"""
			)
		rx = regex.compile(rx, flags=regex.IGNORECASE)

		if url in fetched:
			log(f"already fetched {url}")
			continue
		fetched.append(url)
		log(f"fetching {url} and scanning with {rx.pattern}")

		try:
			with requests.get(url, **REQUEST_OPTS, headers=HEADERS_ACCEPT) as resp:
				if not resp.ok:
					log(f"Request failed: {resp.status_code} ({resp.reason})")
				versions |= set(Version(x.group(0).replace("_", ".")) for x in rx.finditer(resp.text))
		except requests.RequestException as e:
			log(f"Request failed: {e.__class__.__name__}")

	versions = sorted(versions)
	curr_version = Version(version)
	for ver in versions:
		if VERBOSE:
			print(f"found version {ver}")

		consider = check_ignore(ver, ignore)

		if consider and ver > curr_version:
			print(f"{sourcepkg}-{version} -> {sourcepkg}-{ver}")
