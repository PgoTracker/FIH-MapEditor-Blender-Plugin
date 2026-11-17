using System;
using System.Linq;
using FIHMapEditor;

if (args.Length != 1) throw new ArgumentException("Pass the exported .fihmap.zip path.");
var map = MapPackage.Read(args[0]);
foreach (var asset in map.PackageAssets)
{
    var mesh = ObjGeometry.Parse(asset.Geometry);
    if (mesh.Triangles.Length == 0) throw new Exception("Empty geometry: " + asset.Name);
    if (asset.Texture != null) PngTexture.Decode(asset.Texture);
}
Console.WriteLine($"FIH_READER_PASS {map.Name}: {map.Objects.Count} placements, {map.PackageAssets.Count} assets");
