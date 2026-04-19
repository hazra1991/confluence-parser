
from atlassian import Confluence
from functools import lru_cache
from dataclasses import dataclass,field
from bs4 import Tag,BeautifulSoup
from io import BytesIO

@dataclass
class Link:
    text: str
    href: str
    is_attachment: bool = False


@dataclass
class Cell:
    """A single uning of cell,all fields can be emppty"""
    text:str | None = None  
    links: list[Link] = field(default_factory=list)
    tables:list["Table"] = field(default_factory=list)
    # dates: list[str] = field(default_factory=list)    

@dataclass
class Table:
    index:int
    headers: list[Cell] = field(default_factory=list)
    rows: list[list[Cell]] = field(default_factory=list)

class confluenceParser:
    def __init__(self,project_url:str,space_key:str,username:str,password:str):
        self.space_key: str = space_key
        self._page_id: int | None = None
        self._confluence = Confluence(
            url=project_url,
            username=username,
            password=password,
        )
    
    @lru_cache
    def _get_page_id(self,page_title)->int:
        self._page_id =  self._confluence.get_page_id(self.space_key,page_title)
        return self._page_id

    def get_page(self,page_title:str):
        page_id = self._get_page_id(page_title)
        # TODO will check if we can create a page object from the entire page
        # and then link tables and other page related informatinos to it and present it as an single objects
        self._page_content_view = self._confluence.get_page_by_id(page_id, expand="body.view")["body"]["view"]["value"]

    def _parse_cells(self, cell_tags: list[Tag]) -> list[Cell]:
        parsed = []
        for cell in cell_tags:
            cell_obj = Cell(
                text=cell.get_text(" ", strip=True),
                links=[
                    Link(text=a.get_text(strip=True), href=a.get("href", ""))
                    for a in cell.find_all("a", href=True)
                ],
            )
            # Only direct nested tables (not tables inside nested tables)
            direct_tables = [
                t for t in cell.find_all("table")
                if t.find_parent(["td", "th"]) is cell
            ]
            if direct_tables:
                cell_obj.tables = self._parse_tables(direct_tables)
            parsed.append(cell_obj)
        return parsed

    def _parse_tables(self, table_tags: list[Tag]) -> list[Table]:
        parsed = []
        for idx, table in enumerate(table_tags, start=1):
            table_obj = Table(index=idx)
            for row in table.find_all("tr"):
                ths = row.find_all("th", recursive=False)
                tds = row.find_all("td", recursive=False)
                
                if ths and not tds:
                    table_obj.headers = self._parse_cells(ths)
                elif tds:
                    table_obj.rows.append(self._parse_cells(ths + tds))
            parsed.append(table_obj)
        return parsed
    

    def get_tables_from_page(self, page_title):
        page_id = self._get_page_id(page_title)
        page_content = self._confluence.get_page_by_id(page_id, expand="body.view")["body"]["view"]["value"]

        if page_content:
            tables = BeautifulSoup(page_content, "lxml")
            top_level = [
                t for t in tables.find_all("table")
                if t.find_parent(["td", "th"]) is None
            ]
            if not top_level:
                return {"status":404, "msg":"table not found"}
            return self._parse_tables(top_level)

    def download_attachment_from_link(self,link_obj:Link)->BytesIO:
        if "/download/attachments" in link_obj.href:
            response = self._confluence.get(str(link_obj.href), not_json_response=True)
            return BytesIO(response)
        else:
            raise ValueError(f"the link {link_obj.href} is not an attachment")



if __name__ == "__main__":
    confluence = confluenceParser(
        project_url="https://url-to-confluence-page",
        space_key='Space key on confluence',
        username='username-for-confluence',
        password='password-for-confluence'
    )
    breakpoint()
    tables = confluence.get_tables_from_page("page-title-for-confluence")
    link = tables[0].rows[0][2].links[0]
    confluence.download_attachment_from_link(link)
    breakpoint()