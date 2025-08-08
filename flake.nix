{
  description = "yuribot - A Telegram channel submission bot";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs, ... }:
    let
      forAllSystems = nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
      ];
    in
    {
      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt-tree);
      packages = forAllSystems (system: {
        default = self.packages.${system}.yuribot;
        yuribot = nixpkgs.legacyPackages.${system}.callPackage (
          { python3Packages }:
          python3Packages.buildPythonApplication {
            name = "yuribot";
            pyproject = true;
            build-system = [ python3Packages.setuptools ];
            dependencies = [
              python3Packages.aiogram
              python3Packages.beautifulsoup4
              python3Packages.requests
              python3Packages.yt-dlp
            ];
            src = ./.;
            meta.mainProgram = "yuribot";
          }
        ) { };
      });
    };
}
