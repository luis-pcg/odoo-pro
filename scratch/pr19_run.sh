#!/bin/zsh
set -u
ROOT=/Users/luisfernandez/repos/dev_env_odoo_pro-17/scratch
cd /Users/luisfernandez/repos/dev_env_odoo_pro-19/odoo-pro
ORIG=$(git branch --show-current)
DBARGS='--db_host=$DB_PORT_5432_TCP_ADDR --db_port=5432 --db_user=$DB_ENV_POSTGRES_USER --db_password=$DB_ENV_POSTGRES_PASSWORD'
odoo_run(){ docker exec lfernandez_v19 sh -c "odoo -c /etc/odoo/odoo.conf $DBARGS --http-port=8098 --stop-after-init $*"; }
odoo_sh(){ docker exec -i lfernandez_v19 sh -c "odoo shell -c /etc/odoo/odoo.conf $DBARGS --no-http --log-level=warn -d $1" < $ROOT/pr19_check.py 2>&1 | grep -E "^(LOCK|INVOICE)"; }
dropall(){ docker exec lfernandez_v19 sh -c 'export PGPASSWORD=$DB_ENV_POSTGRES_PASSWORD; for d in pr19_up pr19_alone pr19_base_alone; do dropdb -h $DB_PORT_5432_TCP_ADDR -U odoo --if-exists $d; done' >/dev/null 2>&1; }
dropall
git checkout -q --detach origin/19.0-fix-hms_sales_origin_order_id-ec
echo "### BASE (#1333) $(git log -1 --format=%h)"
odoo_run "-d pr19_up -i hms_sales,hms_account" > $ROOT/pr19_base.log 2>&1; echo "install exit $?"
odoo_run "-d pr19_base_alone -i hms_sales" > $ROOT/pr19_base_alone.log 2>&1; echo "install alone exit $?"
echo "-- full"; odoo_sh pr19_up
echo "-- alone"; odoo_sh pr19_base_alone
git checkout -q --detach a85789b8
echo "### PR $(git log -1 --format=%h)"
odoo_run "-d pr19_up -u hms_sales,hms_account --test-tags=/hms_sales,/hms_account" > $ROOT/pr19_up.log 2>&1; echo "upgrade+tests exit $?"
grep -E "FAIL: |ERROR: |tests.stats|tests.result| ERROR | CRITICAL " $ROOT/pr19_up.log | cut -c1-220
odoo_run "-d pr19_alone -i hms_sales --test-tags=/hms_sales" > $ROOT/pr19_alone.log 2>&1; echo "alone+tests exit $?"
grep -E "FAIL: |ERROR: |tests.stats|tests.result| ERROR | CRITICAL " $ROOT/pr19_alone.log | cut -c1-220
echo "-- full (upgraded)"; odoo_sh pr19_up
echo "-- alone"; odoo_sh pr19_alone
git checkout -q $ORIG
echo "restored $(git branch --show-current)"
