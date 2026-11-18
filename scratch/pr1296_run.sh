#!/bin/zsh
set -u
ROOT=/Users/luisfernandez/repos/dev_env_odoo_pro-17
cd $ROOT/odoo-pro
ORIG=$(git branch --show-current)
DBARGS='--db_host=$DB_PORT_5432_TCP_ADDR --db_port=5432 --db_user=$DB_ENV_POSTGRES_USER --db_password=$DB_ENV_POSTGRES_PASSWORD'
odoo_run(){ docker exec lfernandez_v17 sh -c "odoo -c /etc/odoo/odoo.conf $DBARGS --http-port=8099 --stop-after-init $*"; }
odoo_sh(){ docker exec -i lfernandez_v17 sh -c "odoo shell -c /etc/odoo/odoo.conf $DBARGS --no-http --log-level=warn -d $1" < $ROOT/scratch/pr1296_check.py 2>&1 | grep -E "^(LOCK|INVOICE|VIEW|ACTION)"; }
docker exec lfernandez_v17 sh -c "PGPASSWORD=\$DB_ENV_POSTGRES_PASSWORD; export PGPASSWORD; for d in test_pr1296 test_pr1296_up test_pr1296_alone pr_base pr_base_alone pr_alone; do dropdb -h \$DB_PORT_5432_TCP_ADDR -U odoo --if-exists \$d; done" 2>/dev/null
git checkout -q --detach origin/17.0
echo "### BASE 17.0 $(git log -1 --format=%h)"
odoo_run "-d pr_base -i hms_sales,hms_account,hms_sale_pos_backend" > $ROOT/scratch/pr_base.log 2>&1; echo "install exit $?"
odoo_run "-d pr_base_alone -i hms_sales" > $ROOT/scratch/pr_base_alone.log 2>&1; echo "install alone exit $?"
echo "-- full"; odoo_sh pr_base
echo "-- alone"; odoo_sh pr_base_alone
git checkout -q pr-1296
echo "### PR $(git log -1 --format=%h)"
odoo_run "-d pr_base -u hms_sales,hms_account,hms_sale_pos_backend --test-tags=/hms_sales,/hms_account,/hms_sale_pos_backend" > $ROOT/scratch/pr_up.log 2>&1; echo "upgrade+tests exit $?"
grep -E "FAIL: |ERROR: |tests.stats|tests.result| ERROR | CRITICAL " $ROOT/scratch/pr_up.log | cut -c1-220
odoo_run "-d pr_alone -i hms_sales --test-tags=/hms_sales" > $ROOT/scratch/pr_alone.log 2>&1; echo "alone+tests exit $?"
grep -E "FAIL: |ERROR: |tests.stats| ERROR | CRITICAL " $ROOT/scratch/pr_alone.log | cut -c1-220
echo "-- full (upgraded)"; odoo_sh pr_base
echo "-- alone"; odoo_sh pr_alone
git checkout -q $ORIG
echo "restored $(git branch --show-current)"
