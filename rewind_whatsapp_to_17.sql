-- Rewind the DB so it looks like it came from the 17.0 branch of the AcruxLab
-- modules (whatsapp_connector 17.0.36.0), after the Odoo upgrade platform ran:
--   * the group "categories" are still ir.module.category records
--   * ir_model_data still points at them with model = 'ir.module.category'
--   * ir_module_module.latest_version still carries the 17.0 module version
DO $$
DECLARE
    r record;
    new_id int;
    parent int;
BEGIN
    SELECT res_id INTO parent
      FROM ir_model_data
     WHERE module = 'whatsapp_connector' AND name = 'category_chatroom';

    -- xmlids that were ir.module.category on 17.0 and are res.groups.privilege on 19.0
    FOR r IN
        SELECT d.id AS data_id, d.res_id
          FROM ir_model_data d
         WHERE d.model = 'res.groups.privilege'
           AND (d.module, d.name) IN (
                ('whatsapp_connector',         'category_chat_access_connector'),
                ('whatsapp_connector',         'category_chat_show_user'),
                ('whatsapp_connector_chatter', 'category_chat_show_chatter'))
    LOOP
        INSERT INTO ir_module_category (name, parent_id, sequence, visible)
        SELECT p.name, parent, p.sequence, true
          FROM res_groups_privilege p WHERE p.id = r.res_id
        RETURNING id INTO new_id;

        UPDATE res_groups SET privilege_id = NULL WHERE privilege_id = r.res_id;
        DELETE FROM res_groups_privilege WHERE id = r.res_id;
        UPDATE ir_model_data SET model = 'ir.module.category', res_id = new_id
         WHERE id = r.data_id;
    END LOOP;

    -- 19.0 renamed category_chat_connector -> privilege_chat_connector; on a 17.0
    -- database only the old xmlid exists
    SELECT d.res_id INTO new_id FROM ir_model_data d
     WHERE d.module = 'whatsapp_connector' AND d.name = 'privilege_chat_connector';
    IF new_id IS NOT NULL THEN
        INSERT INTO ir_module_category (name, parent_id, sequence, visible)
        SELECT p.name, parent, p.sequence, true
          FROM res_groups_privilege p WHERE p.id = new_id
        RETURNING id INTO parent;
        UPDATE res_groups SET privilege_id = NULL WHERE privilege_id = new_id;
        DELETE FROM res_groups_privilege WHERE id = new_id;
        DELETE FROM ir_model_data
         WHERE module = 'whatsapp_connector' AND name = 'privilege_chat_connector';
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        VALUES ('whatsapp_connector', 'category_chat_connector', 'ir.module.category', parent, false);
    END IF;
END $$;

UPDATE ir_module_module SET latest_version = '17.0.36.0' WHERE name = 'whatsapp_connector';
UPDATE ir_module_module SET latest_version = '17.0.3.0'
 WHERE name IN ('whatsapp_connector_chatter', 'whatsapp_connector_crm', 'whatsapp_connector_sale');

SELECT module || '.' || name AS xmlid, model, res_id FROM ir_model_data
 WHERE module LIKE 'whatsapp%' AND model IN ('ir.module.category', 'res.groups.privilege') ORDER BY 1;
SELECT name, latest_version FROM ir_module_module WHERE name LIKE 'whatsapp_connector%' AND state = 'installed' ORDER BY 1;

-- 19.0 renamed conversation_action_tree -> conversation_action_list (and the
-- view_mode from tree to list). A database coming from 17.0 still carries the
-- old xmlid, with view_mode already converted to 'list' by the upgrade.
UPDATE ir_model_data SET name = 'conversation_action_tree'
 WHERE module = 'whatsapp_connector' AND name = 'conversation_action_list'
   AND model = 'ir.actions.act_window.view';
SELECT d.name, v.view_mode, v.sequence, v.act_window_id
  FROM ir_model_data d JOIN ir_act_window_view v ON v.id = d.res_id
 WHERE d.module = 'whatsapp_connector' AND d.model = 'ir.actions.act_window.view';
