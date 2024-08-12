# -*- coding: utf-8 -*-
# from odoo import http


# class KoleksiBuku(http.Controller):
#     @http.route('/koleksi_buku/koleksi_buku', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/koleksi_buku/koleksi_buku/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('koleksi_buku.listing', {
#             'root': '/koleksi_buku/koleksi_buku',
#             'objects': http.request.env['koleksi_buku.koleksi_buku'].search([]),
#         })

#     @http.route('/koleksi_buku/koleksi_buku/objects/<model("koleksi_buku.koleksi_buku"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('koleksi_buku.object', {
#             'object': obj
#         })

