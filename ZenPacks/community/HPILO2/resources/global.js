(function(){

var ZC = Ext.ns('Zenoss.component');

Ext.apply(Zenoss.render, {

    ilo2_memory_frequency: function(value) {
        if (value !== 'N/A' ) {
            return value + ' MHz';
        } else {
            return 'N/A';
        }
    },

    ilo2_temp_celsius: function(value) {
        if (value !== 'N/A' ) {
            return value + ' &#176;C';
        } else {
            return 'N/A';
        }
    }

});
})();
