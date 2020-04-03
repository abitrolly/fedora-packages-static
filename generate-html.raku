#!/usr/bin/raku
#
# Fetch (basic) package metadata from various sources and store in JSON file.
# This data will be used to generate static pages.
#
# Complex data such as requires & friend could be either fetched here or
# asynchronously from the client's browser.
#
# What do we extract, and where:
#
# PDC: store every package name in Fedora, old and new.
#   - Name
#   - Dist-git URL
# MDAPI: interface to repositories.
#   - Summary
#   - Description
#   - Upstream URL
#
# Bugzilla and Bhodi URLs can begenerated from PDC name. Where is license? Does
# not show up by default in MDAPI request...

use Cro::HTTP::Client;

class Package {
	has $.name;
	has $.dist_git_url is rw;
	has $.summary is rw;
	has $.description is rw;
	has $.upstream is rw;
}

sub generate_index(@pkgs) {
	my $header = q:to/END/;
	<!DOCTYPE html>
	<html>
	<body>
	<h1>Fedora Package Index</h1>
	<ul>
	END

	my @links;
	for @pkgs -> $pkg {
		@links.push("<li><a href=\"{$pkg.name}.html\">{$pkg.name}</a></li>");
	}

	my $footer = q:to/END/;
	</ul>
	</body>
	</html>
	END

	return $header ~ join("\n", @links) ~ $footer;
}

sub generate_package_page($pkg) {
	my $header = q:to/END/;
	<!DOCTYPE html>
	<html>
	<body>
	END

	my @lines = [
		"<h1>Package: {$pkg.name}</h1>",
		"<ul>",
		"<li>{$pkg.summary}</li>",
		"<li><a href=\"{$pkg.upstream}\">{$pkg.upstream}</a></li>",
		"<li><a href=\"{$pkg.dist_git_url}\">{$pkg.dist_git_url}</a></li>",
		"</ul>",
		"<p>{$pkg.description}</p>"
	];

	my $footer = q:to/END/;
	</body>
	</html>
	END

	return $header ~ join("\n", @lines) ~ $footer;
}

my @pkgs;
my $client = Cro::HTTP::Client.new(
	headers => [
		User-agent => 'Cro'
	]);

print "Fetching packages from PDC...";

my $pdc_resp = await Cro::HTTP::Client.get('https://pdc.fedoraproject.org/rest_api/v1/global-components/');
my $pdc_body = await $pdc_resp.body;

for $pdc_body<results> -> @entries {
	for @entries -> $entry {
		@pkgs.push(Package.new(name => $entry<name>, dist_git_url => $entry<dist_git_web_url>));
	}
}

say " extracted {@pkgs.elems} names.";

for @pkgs -> $pkg {
		my $body;
		try {
			say "Fetching {$pkg.name} metadata from mdapi...";
			my $resp = await Cro::HTTP::Client.get("https://mdapi.fedoraproject.org/rawhide/pkg/{$pkg.name}");
			$body = await $resp.body;

			$pkg.summary = $body<summary>;
			$pkg.description = $body<description>;
			$pkg.upstream = $body<url>;
		}
}

say "Generating HTML...";

mkdir "html";
spurt "html/index.html", generate_index(@pkgs);
for @pkgs -> $pkg {
	spurt "html/{$pkg.name}.html", generate_package_page($pkg);
}
