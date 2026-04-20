from odoo import models, fields, api
from odoo.exceptions import UserError
class ShopifySyncWizard(models.TransientModel):
    _name = 'shopify.sync.wizard'
    _description = 'Wizard đồng bộ Shopify'

    # Cho phép người dùng chọn cửa hàng muốn sync
    config_id = fields.Many2one('shopify.config', string="Cửa hàng", required=True)
    
    sync_type = fields.Selection([
        ('product', 'Đồng bộ Sản phẩm (chỉ mới/cập nhật)'),
        ('product_full', 'Đồng bộ Toàn bộ Sản phẩm'),
        ('order', 'Nhập Đơn hàng')
    ], string="Loại đồng bộ", default='product')

    def action_sync(self):
        """Nút bấm thực hiện hành động"""
        # Đảm bảo đã chọn cửa hàng
        if not self.config_id:
            raise UserError("Vui lòng chọn một cửa hàng để đồng bộ!")

        if self.sync_type == 'product':
            return self.config_id.import_products()
        elif self.sync_type == 'product_full':
            return self.config_id.sync_all_products()
        else:
            return self.config_id.import_orders_with_notification()
