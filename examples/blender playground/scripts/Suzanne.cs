using FIHMapEditor;
using UnityEngine;

public class Suzanne : IPackagedGeometryBehavior
{
    public void OnSpawn(PackagedGeometryContext context)
    {
        if (!context.EnablePackagedImpactSound(
                minImpulse: 0.2f, cooldown: 0.3f, volume: 1f))
        {
            Debug.LogWarning("[PACKAGE] Suzanne.wav is missing from this map package.");
        }
    }

    public void Update(PackagedGeometryContext context, float deltaTime) { }

    public void OnDespawn(PackagedGeometryContext context) { }
}
