function setTheme(dark) {
    if (dark) {document.documentElement.setAttribute('theme', 'dark');}
    else {document.documentElement.setAttribute('theme', 'light');}
}
const darktheme = window.matchMedia("(prefers-color-scheme: dark)");
setTheme(darktheme.matches);
darktheme.addListener(theme => {setTheme(theme.matches);});

const serverTime = new Date("{{streamTime}} *1000");
var recording = false;

function flipBlinking(element) {
    recPastSecs = document.getElementById('recPastSecs');
    if (recording === true) {
        document.getElementById('download_vid').click();
        element.className = "menuBox";
        recPastSecs.className = "menuBox";
        recPastSecs.disabled = false;
        recording=false;
    } else {
        new Image().src = '{{url_for("download_current_vid")}}';
        element.className = "menuBox startRecBlinking";
        recPastSecs.className = "menuBox unclickable";
        recPastSecs.disabled = true;
        recording=true;
    }
    console.log(recPastSecs.disabled);
}

function downloadImg() {
    document.getElementById('download_img').click();
}
function downloadVid(element) {
    flipBlinking(element)
}
function downloadPastVid() {
    document.getElementById('download_pastvid').click();
}