const { decorateStock } = require('../../utils/inventory');
const { getMessages, t } = require('../../utils/i18n');

Component({
  properties: {
    material: {
      type: Object,
      value: null,
      observer(material) {
        this.updateDisplayMaterial(material);
      },
    },
  },

  data: {
    displayMaterial: null,
    i18n: getMessages(),
  },

  methods: {
    updateDisplayMaterial(material) {
      if (!material) {
        this.setData({ displayMaterial: null });
        return;
      }
      this.setData({
        displayMaterial: {
          ...decorateStock(material),
          minimum_stock_label:
            material.minimum_qty === null || material.minimum_qty === undefined
              ? ''
              : t('minimumStock', {
                  quantity: material.minimum_qty,
                  unit: material.unit_name,
                }),
        },
      });
    },
  },
});
