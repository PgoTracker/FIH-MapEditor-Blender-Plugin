using FIHMapEditor;
using UnityEngine;

public class Platform : IPackagedGeometryBehavior
{
    private bool _carrying;

     public void OnSpawn(PackagedGeometryContext context)
    {
        context.SetGroundSurface(PackagedGroundSurface.HardMetal);
        context.SetColliderPhysics(staticFriction: 99f, dynamicFriction: 99f,
                                   bounciness: 0.05f);
        if (!context.EnablePackagedImpactSound(minImpulse: 0.5f, cooldown: 0.2f,
                                               volume: 0.6f))
            Debug.LogWarning("[PACKAGE] Spinner's matching impact sound is missing.");
        Debug.Log("[PACKAGE] Spinner ground: HardMetal; physics and packaged impact enabled.");
    }

    public void Update(PackagedGeometryContext context, float deltaTime)
    {
        var root = context.Root;
        if (root == null) return;

        var player = context.LocalPlayer;
        Collider playerCollider = null;
        if (player != null)
            foreach (var collider in player.GetComponentsInChildren<Collider>(false))
                if (collider != null && collider.enabled && !collider.isTrigger)
                { playerCollider = collider; break; }
        var platformCollider = root.GetComponentInChildren<Collider>(false);
        bool standingOnTop = false;
        if (playerCollider != null && platformCollider != null)
        {
            var bounds = playerCollider.bounds;
            var ray = new Ray(bounds.center, Vector3.down);
            RaycastHit hit;
            standingOnTop = platformCollider.Raycast(ray, out hit, bounds.extents.y + 0.3f)
                && hit.normal.y > 0.5f
                && Mathf.Abs(bounds.min.y - hit.point.y) < 0.25f;
        }

        var pivot = root.transform.position;
        var turn = Quaternion.AngleAxis(45f * deltaTime, Vector3.up);
        root.transform.rotation = turn * root.transform.rotation;

        if (standingOnTop && !_carrying) Debug.Log("[PACKAGE] Platform is carrying the local player.");
        _carrying = standingOnTop;
        if (!standingOnTop) return;
        var body = player.GetComponent<Rigidbody>();
        if (body != null)
        {
            body.position = pivot + turn * (body.position - pivot);
            body.rotation = turn * body.rotation;
        }
        else
        {
            player.transform.position = pivot + turn * (player.transform.position - pivot);
            player.transform.rotation = turn * player.transform.rotation;
        }
    }

    public void OnDespawn(PackagedGeometryContext context) { }
}
