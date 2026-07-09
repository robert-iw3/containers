// CIS: Create per-tenant RBAC (no root access for apps)
// Params from env: NUM_TENANTS=100, TENANT_PREFIX='tenant_', APP_USER_ROLE='readWrite'

var numTenants = parseInt(db.getSiblingDB('admin').runCommand({getParameter: 1, numTenants: 1}).numTenants) || 100;
var prefix = db.getSiblingDB('admin').runCommand({getParameter: 1, tenantPrefix: 1}).tenantPrefix || 'tenant_';
var role = 'readWrite';  // Custom role per CIS 2.5

for (var i = 1; i <= numTenants; i++) {
  var dbName = prefix + i;
  var user = 'app_user_' + i;
  var pwd = 'strong_password_' + i;  // In prod: From secrets/Vault

  // Create DB
  db.getSiblingDB(dbName).createCollection('metadata');

  // Custom role: CIS 2.5 - Least privilege
  db.getSiblingDB('admin').createRole('tenantRole_' + i, {
    privileges: [{ resource: { db: dbName, collection: '' }, actions: [role] }],
    roles: []
  });

  // Create user with role
  db.getSiblingDB(dbName).createUser({
    user: user,
    pwd: pwd,
    roles: [{ role: 'tenantRole_' + i, db: 'admin' }]
  });

  print('Tenant ' + dbName + ' provisioned with user ' + user);
}

// For sharded: Add shard key index per tenant DB (e.g., hashed on _id)