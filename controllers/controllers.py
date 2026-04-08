# from odoo import http


# class ShopifyIntegration(http.Controller):
#     @http.route('/shopify_integration/shopify_integration', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/shopify_integration/shopify_integration/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('shopify_integration.listing', {
#             'root': '/shopify_integration/shopify_integration',
#             'objects': http.request.env['shopify_integration.shopify_integration'].search([]),
#         })

#     @http.route('/shopify_integration/shopify_integration/objects/<model("shopify_integration.shopify_integration"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('shopify_integration.object', {
#             'object': obj
#         })

