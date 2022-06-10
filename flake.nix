{
  description = "XMonad like sway layouts";

  inputs.utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs";

  outputs = { self, nixpkgs, utils }:
    utils.lib.eachSystem [ "x86_64-linux" "aarch64-linux" ] (system:
      let pkgs = nixpkgs.legacyPackages.${system};
      in {
        packages.swaymonad = pkgs.stdenv.mkDerivation {
          pname = "swaymonad";
          version = "0.0.1";
          buildInputs = [
            (pkgs.python310.withPackages
              (pythonPackages: with pythonPackages; [ i3ipc ]))
          ];
          unpackPhase = "true";
          buildPhase = "true";
          installPhase = ''
            mkdir -p $out/usr/swaymonad
            cp ${./.}/*.py $out/usr/swaymonad
            mkdir -p $out/bin
            ln -s $out/usr/swaymonad/swaymonad.py $out/bin/swaymonad
          '';
        };

        defaultPackage = self.packages.${system}.swaymonad;
      });
}
